// messages-link: the assistant's one link to the owner's Google Messages (SMS and RCS), built on libgm from
// go.mau.fi/mautrix-gmessages (pinned in go.mod, used unchanged; nothing of Matrix is used).
//
// The page server (System\live\textlink.py, inside the listener) starts it hidden and talks to it over this program's
// standard input and output, one JSON object per line; it ends when its input closes, so it stops with the server.
// It never opens the database: every message it receives is handed to the server, which stores it.
//
//	server -> link   {"cmd": "since", "us": N}                       the newest stored text's time (earlier: a picture placeholder's); catch-up starts there
//	                 {"cmd": "status", "rid": R}                      the state now
//	                 {"cmd": "pair", "rid": R, "cookies": {...}}      sign in with Google-account cookies; replies with the emoji
//	                 {"cmd": "cancel_pair", "rid": R}
//	                 {"cmd": "send", "rid": R, "conv": C, "phone": P, "text": T, "tmp": X}
//	                 {"cmd": "catchup", "rid": R}
//	                 {"cmd": "browser", "mode": "yield" | "take_back"}   what to do when a browser takes the session
//	                 {"cmd": "take_back", "rid": R}                    take the session back from a browser (then catch up)
//	                 {"cmd": "convs", "rid": R}                        the conversation list (inbox and archive), for matching
//	link -> server   {"type": "reply", "rid": R, ...}                 the answer to one command
//	                 {"type": "state", "state": S, "say": ..., ...}   whenever the connection's state changes
//	                 {"type": "message", "row": {...}}               one received or sent text, as the server stores it
//
// What it keeps: --auth <file>, the pairing and cookies (AuthData), the SIM cards from the phone's settings, the owner's
// own participant ids and the conversations that must be sent as RCS. Pictures and files of received texts are written
// to --media <folder> and named in the row; the server takes them from there.
//
// --test: no connection to Google at all. The commands "fake" (a conversation and a message as protojson, passed through
// the same handler real events go through) and "form_send" (the send request that would be sent, as protojson) are
// added, for the acceptance test.
//
// Build (from this folder): go build -trimpath -buildvcs=false -ldflags "-s -w -H=windowsgui" -o messages-link.exe .
// libgm is AGPL-3.0, so this program is too; it is for the owner's own computer.
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"mime"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/rs/zerolog"
	"go.mau.fi/util/exhttp"
	"google.golang.org/protobuf/encoding/protojson"

	"go.mau.fi/mautrix-gmessages/pkg/libgm"
	"go.mau.fi/mautrix-gmessages/pkg/libgm/events"
	"go.mau.fi/mautrix-gmessages/pkg/libgm/gmproto"
	"go.mau.fi/mautrix-gmessages/pkg/libgm/util"
)

// ---------------------------------------------------------------------------------------------------------------
// output to the server

var outMu sync.Mutex
var out = json.NewEncoder(os.Stdout)

func emit(v map[string]any) {
	outMu.Lock()
	defer outMu.Unlock()
	_ = out.Encode(v)
}

func reply(rid string, v map[string]any) {
	if v == nil {
		v = map[string]any{}
	}
	v["type"], v["rid"] = "reply", rid
	emit(v)
}

// ---------------------------------------------------------------------------------------------------------------
// what is kept between runs

type saved struct {
	Auth     *libgm.AuthData            `json:"auth,omitempty"`
	SIMs     map[string]json.RawMessage `json:"sims,omitempty"` // participant id -> SIMCard (protojson)
	SelfIDs  []string                   `json:"self_ids,omitempty"`
	ForceRCS map[string]bool            `json:"force_rcs,omitempty"`
	Signed   bool                       `json:"signed_in_once,omitempty"`
}

type link struct {
	mu         sync.Mutex
	saveMu     sync.Mutex
	path       string
	mediaDir   string
	test       bool
	st         saved
	sims       map[string]*gmproto.SIMCard
	cli        *libgm.Client
	log        zerolog.Logger
	ctx        context.Context
	state      string // signed_out, pairing, connecting, connected, browser_open, phone_not_responding, signed_out_by_google, unpaired, error
	say        string
	since      time.Time // the newest text the server holds when it started
	lastData   time.Time
	ready      bool
	responding bool
	inactive   bool
	yield      bool // the owner lets a browser have the session: wait (state browser_open) until the server says take it back
	noData     bool
	sessionID  string
	didHacky   bool
	convs      map[string]*gmproto.Conversation
	seen       map[string]int  // handed over: 1 its words, its picture not ready yet; 2 with a picture at thumbnail size, its full size asked for; 3 whole
	fullAsked  map[string]bool // the full size asked for (message id|part id), once while this program runs, as the bridge's fullMediaRequests
	queue      chan *libgm.WrappedMessage
	pairCli    *libgm.Client
	pairStop   context.CancelFunc
	emoji      string
	catching   bool
	stalling   bool
}

func (l *link) load() {
	data, err := os.ReadFile(l.path)
	if err == nil {
		if err = json.Unmarshal(data, &l.st); err != nil {
			l.log.Warn().Err(err).Msg("the saved sign-in could not be read; starting signed out")
			l.st = saved{}
		}
	}
	l.sims = map[string]*gmproto.SIMCard{}
	for id, raw := range l.st.SIMs {
		var sim gmproto.SIMCard
		if protojson.Unmarshal(raw, &sim) == nil {
			l.sims[id] = &sim
		}
	}
	if l.st.ForceRCS == nil {
		l.st.ForceRCS = map[string]bool{}
	}
}

// save writes the kept state whole to a new file and moves it over the old one, so a cut-off write never leaves half a file.
func (l *link) save() {
	if l.test {
		return
	}
	l.saveMu.Lock()
	defer l.saveMu.Unlock()
	l.mu.Lock()
	l.st.SIMs = map[string]json.RawMessage{}
	for id, sim := range l.sims {
		if raw, err := protojson.Marshal(sim); err == nil {
			l.st.SIMs[id] = raw
		}
	}
	data, err := json.Marshal(&l.st)
	l.mu.Unlock()
	if err != nil {
		l.log.Err(err).Msg("the sign-in could not be written")
		return
	}
	tmp := l.path + ".new"
	if err = os.WriteFile(tmp, data, 0o600); err == nil {
		err = os.Rename(tmp, l.path)
	}
	if err != nil {
		l.log.Err(err).Msg("the sign-in could not be saved")
	}
}

func (l *link) setState(state, say string) {
	l.mu.Lock()
	changed := l.state != state || l.say != say
	l.state, l.say = state, say
	l.mu.Unlock()
	if changed {
		l.log.Info().Str("state", state).Msg("state")
		emit(l.statusMap("state"))
	}
}

func (l *link) statusMap(kind string) map[string]any {
	l.mu.Lock()
	defer l.mu.Unlock()
	m := map[string]any{"type": kind, "state": l.state, "say": l.say, "ready": l.ready, "phone_responding": l.responding,
		"signed_in_once": l.st.Signed, "paired": l.st.Auth != nil && l.st.Auth.PairingID != uuid.Nil, "sims": len(l.sims)}
	if !l.lastData.IsZero() {
		m["last_data"] = l.lastData.Format(time.RFC3339)
	}
	if l.state == "pairing" {
		m["emoji"] = l.emoji
	}
	return m
}

// ---------------------------------------------------------------------------------------------------------------
// connecting with the saved sign-in

func (l *link) newClient(ad *libgm.AuthData) *libgm.Client {
	cli := libgm.NewClient(ad, nil, l.log.With().Str("part", "libgm").Logger(), exhttp.SensibleClientSettings)
	cli.SetEventHandler(l.handle)
	return cli
}

func (l *link) connect() {
	ad := l.st.Auth
	switch {
	case ad == nil || !ad.HasCookies() && ad.IsGoogleAccount():
		l.signedOut()
		return
	case ad.PairingID == uuid.Nil || ad.TachyonAuthToken == nil:
		l.signedOut()
		return
	}
	cli := l.newClient(ad)
	l.mu.Lock()
	l.cli, l.ready, l.responding, l.inactive, l.didHacky = cli, false, true, false, false
	l.mu.Unlock()
	l.setState("connecting", "")
	wait := 30 * time.Second
	for {
		err := cli.FetchConfig(l.ctx)
		if err == nil && ad.IsGoogleAccount() && cli.Config.GetDeviceInfo().GetEmail() == "" {
			l.invalidate(false, true, "Google no longer accepts this computer's sign-in.")
			return
		}
		if err != nil {
			l.log.Warn().Err(err).Msg("config not fetched")
		}
		err = cli.Connect(l.ctx)
		if err == nil {
			go l.keepSaving(cli)
			return
		}
		if l.credentialError(err) {
			return
		}
		l.setState("connecting", "Could not reach Google Messages ("+short(err)+"); trying again.")
		select {
		case <-l.ctx.Done():
			return
		case <-time.After(wait):
		}
		if wait < 10*time.Minute {
			wait *= 2
		}
	}
}

// reconnectLater ends the client in use and connects again after a minute, unless another client has taken its place.
func (l *link) reconnectLater() {
	l.mu.Lock()
	cli := l.cli
	l.mu.Unlock()
	if cli == nil {
		return
	}
	cli.SetEventHandler(func(any) {})
	cli.Disconnect()
	select {
	case <-l.ctx.Done():
		return
	case <-time.After(time.Minute):
	}
	l.mu.Lock()
	same := l.cli == cli
	l.mu.Unlock()
	if same {
		l.connect()
	}
}

func (l *link) signedOut() {
	if l.st.Signed {
		l.setState("signed_out_by_google", "Google Messages is no longer signed in on this computer.")
	} else {
		l.setState("signed_out", "")
	}
}

// keepSaving saves the sign-in every half hour while this client is the one in use (its tokens are refreshed on the way).
func (l *link) keepSaving(cli *libgm.Client) {
	t := time.NewTicker(30 * time.Minute)
	defer t.Stop()
	for {
		select {
		case <-l.ctx.Done():
			return
		case <-t.C:
			l.mu.Lock()
			same := l.cli == cli
			l.mu.Unlock()
			if !same {
				return
			}
			l.save()
		}
	}
}

// credentialError ends the session as the bridge does when err says the pairing or the cookies are no longer good.
func (l *link) credentialError(err error) bool {
	var httpErr events.HTTPError
	switch {
	case errors.Is(err, events.ErrRequestedEntityNotFound):
		l.invalidate(true, false, "Your phone is no longer paired with this computer.")
	case errors.Is(err, events.ErrInvalidCredentials):
		l.invalidate(false, true, "Google signed this computer out of Google Messages.")
	case errors.As(err, &httpErr) && httpErr.Action == "polling" && httpErr.Resp != nil && httpErr.Resp.StatusCode == http.StatusUnauthorized:
		l.invalidate(false, true, "Google signed this computer out of Google Messages.")
	default:
		return false
	}
	return true
}

func (l *link) invalidate(pairing, cookies bool, say string) {
	l.mu.Lock()
	cli := l.cli
	l.cli, l.ready = nil, false
	if l.st.Auth != nil {
		if pairing && cookies {
			l.st.Auth = nil
		} else if pairing {
			l.st.Auth.ClearPairing()
		} else {
			l.st.Auth.SetCookies(nil)
		}
	}
	l.mu.Unlock()
	if cli != nil {
		cli.SetEventHandler(func(any) {})
		cli.Disconnect()
	}
	l.save()
	state := "signed_out_by_google"
	if pairing {
		state = "unpaired"
	}
	l.setState(state, say)
}

// ---------------------------------------------------------------------------------------------------------------
// events from libgm (called synchronously: nothing here waits on Google)

func (l *link) handle(raw any) {
	switch evt := raw.(type) {
	case *events.ListenFatalError:
		// as the bridge does, the session is ended away from libgm's own callback; anything but a sign-in fault is tried again
		go func(err error) {
			if !l.credentialError(err) {
				l.setState("error", "The connection to Google Messages stopped ("+short(err)+"); trying again in a minute.")
				l.reconnectLater()
			}
		}(evt.Error)
	case *events.ListenTemporaryError:
		l.setState("connecting", "Trouble reaching Google Messages ("+short(evt.Error)+"); trying again.")
	case *events.ListenRecovered:
		l.mu.Lock()
		ready := l.ready
		l.mu.Unlock()
		if ready {
			l.setState("connected", "")
		}
	case *events.PhoneNotResponding:
		l.mu.Lock()
		l.responding = false
		l.mu.Unlock()
		l.setState("phone_not_responding", "Your phone is not answering Google Messages.")
	case *events.PhoneRespondingAgain:
		l.mu.Lock()
		l.responding = true
		ready := l.ready
		l.mu.Unlock()
		if ready {
			l.setState("connected", "")
		} else {
			l.setState("connecting", "")
		}
	case *events.HackySetActiveMayFail:
		go l.hackyResetActive()
	case *events.PingFailed:
		if errors.Is(evt.Error, events.ErrRequestedEntityNotFound) {
			go l.invalidate(true, false, "Your phone is no longer paired with this computer.")
		} else if evt.ErrorCount > 1 {
			l.setState("connecting", "Google Messages is not answering ("+short(evt.Error)+").")
		}
	case *gmproto.RevokePairData:
		go l.invalidate(true, false, "This computer was unpaired from Google Messages on your phone.")
	case *events.GaiaLoggedOut:
		go l.invalidate(true, false, "Google Messages on your phone was signed out of this computer.")
	case *events.AuthTokenRefreshed:
		go l.save()
	case *gmproto.Conversation:
		l.noteConv(evt)
		l.gotData(time.Time{})
	case *libgm.WrappedMessage:
		l.gotData(time.UnixMicro(evt.GetTimestamp()))
		if evt.GetMessageStatus().GetStatus() == gmproto.MessageStatusType_MESSAGE_DELETED {
			return
		}
		select {
		case l.queue <- evt:
		default:
			go func() { l.queue <- evt }()
		}
	case *gmproto.UserAlertEvent:
		l.alert(evt)
	case *gmproto.Settings:
		l.settings(evt)
	case *events.NoDataReceived:
		l.mu.Lock()
		l.noData = true
		l.mu.Unlock()
		go l.recoverStall()
	case *events.AccountChange, *events.PairSuccessful:
		l.log.Debug().Type("event", raw).Msg("event")
	default:
		l.log.Trace().Type("event", raw).Msg("event not used")
	}
}

// gotData notes that data arrives; data after a stretch of none means texts may have been missed: catch up.
func (l *link) gotData(ts time.Time) {
	l.mu.Lock()
	was, anchor := l.noData, l.lastData
	l.noData = false
	if ts.After(l.lastData) {
		l.lastData = ts
	}
	back := l.ready && l.responding && !l.inactive && l.cli != nil && l.state != "connected"
	l.mu.Unlock()
	if back {
		l.setState("connected", "") // data flows again after a passing trouble
	}
	if was {
		go l.catchUp(anchor)
	}
}

func (l *link) noteConv(c *gmproto.Conversation) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.convs[c.GetConversationID()] = c
	for _, p := range c.GetParticipants() {
		id := p.GetID().GetParticipantID()
		if p.GetIsMe() && id != "" && !contains(l.st.SelfIDs, id) {
			l.st.SelfIDs = append(l.st.SelfIDs, id)
		}
	}
}

func (l *link) alert(v *gmproto.UserAlertEvent) {
	l.mu.Lock()
	cli := l.cli
	inactive := false
	resync := false
	anchor := l.lastData
	switch v.GetAlertType() {
	case gmproto.AlertType_BROWSER_INACTIVE, gmproto.AlertType_BROWSER_INACTIVE_FROM_TIMEOUT, gmproto.AlertType_BROWSER_INACTIVE_FROM_INACTIVITY:
		l.inactive, inactive = true, true
	case gmproto.AlertType_BROWSER_ACTIVE:
		wasInactive := l.inactive || !l.ready
		l.inactive, l.ready = false, true
		newID := ""
		if cli != nil {
			newID = cli.CurrentSessionID()
		}
		if newID != l.sessionID || wasInactive || l.noData {
			resync = true
		}
		l.sessionID, l.noData = newID, false
	case gmproto.AlertType_MOBILE_DATABASE_SYNC_COMPLETE:
		resync = true
	default:
		l.mu.Unlock()
		return
	}
	responding := l.responding
	l.mu.Unlock()
	if inactive {
		l.mu.Lock()
		yield := l.yield
		l.mu.Unlock()
		if yield {
			// the owner chose to let a browser have it: wait; Google sends no word when that tab closes, so the server's
			// 15-minute check says when to take it back (take_back)
			l.setState("browser_open", "Paused while Messages is open in your browser.")
			return
		}
		// Google Messages was opened in another browser, which takes over: take it back, as the bridge's aggressive reconnect does
		l.setState("connecting", "Google Messages was opened somewhere else; taking it back.")
		go l.aggressiveSetActive()
		return
	}
	if responding {
		l.setState("connected", "")
	}
	if resync {
		go l.catchUp(anchor)
	}
}

func (l *link) aggressiveSetActive() {
	for _, s := range []int{5, 10, 30} {
		select {
		case <-l.ctx.Done():
			return
		case <-time.After(time.Duration(s) * time.Second):
		}
		l.mu.Lock()
		cli, inactive := l.cli, l.inactive
		l.mu.Unlock()
		if !inactive || cli == nil {
			return
		}
		if err := cli.SetActiveSession(l.ctx); err != nil {
			l.log.Warn().Err(err).Msg("could not set this computer active")
		} else {
			return
		}
	}
	l.setState("error", "Google Messages is open in another browser and this computer could not take it back.")
}

func (l *link) hackyResetActive() {
	l.mu.Lock()
	if l.didHacky {
		l.mu.Unlock()
		return
	}
	l.didHacky = true
	l.mu.Unlock()
	for i := 0; i < 2; i++ {
		time.Sleep(7 * time.Second)
		l.mu.Lock()
		cli, ready, responding := l.cli, l.ready, l.responding
		l.mu.Unlock()
		if ready || !responding || cli == nil {
			return
		}
		if i == 0 {
			if err := cli.SetActiveSession(l.ctx); err != nil {
				l.log.Err(err).Msg("could not set this computer active again")
			}
			continue
		}
		l.log.Warn().Msg("still not ready; connecting again")
		cli.SetEventHandler(func(any) {})
		cli.Disconnect()
		go l.connect()
	}
}

func (l *link) recoverStall() {
	l.mu.Lock()
	if l.stalling {
		l.mu.Unlock()
		return
	}
	l.stalling = true
	l.mu.Unlock()
	defer func() { l.mu.Lock(); l.stalling = false; l.mu.Unlock() }()
	for attempt := 0; attempt < 3; attempt++ {
		select {
		case <-l.ctx.Done():
			return
		case <-time.After(time.Minute):
		}
		l.mu.Lock()
		cli, noData, ok := l.cli, l.noData, l.ready && l.responding && !l.inactive
		l.mu.Unlock()
		if cli == nil || !noData || !ok {
			return
		}
		l.mu.Lock()
		anchor := l.lastData
		l.mu.Unlock()
		if gap := l.catchUp(anchor); !gap {
			return
		}
		if attempt == 0 {
			_ = cli.SetActiveSession(l.ctx)
		} else if attempt == 1 {
			_ = cli.Reconnect(l.ctx)
		}
	}
}

func (l *link) settings(s *gmproto.Settings) {
	if s.GetSIMCards() == nil {
		return
	}
	l.mu.Lock()
	changed := len(s.GetSIMCards()) != len(l.sims)
	sims := map[string]*gmproto.SIMCard{}
	for _, sim := range s.GetSIMCards() {
		id := sim.GetSIMParticipant().GetID()
		if old := l.sims[id]; old == nil || old.GetSIMData().GetSIMPayload().GetSIMNumber() != sim.GetSIMData().GetSIMPayload().GetSIMNumber() {
			changed = true
		}
		sims[id] = sim
		if id != "" && !contains(l.st.SelfIDs, id) {
			l.st.SelfIDs = append(l.st.SelfIDs, id)
		}
	}
	l.sims = sims
	l.mu.Unlock()
	if changed {
		go l.save()
	}
}

// ---------------------------------------------------------------------------------------------------------------
// received texts -> rows for the server

func (l *link) messages() {
	for {
		select {
		case <-l.ctx.Done():
			return
		case m := <-l.queue:
			l.process(m)
		}
	}
}

func (l *link) conv(id string) *gmproto.Conversation {
	l.mu.Lock()
	c, cli := l.convs[id], l.cli
	l.mu.Unlock()
	if c != nil || cli == nil || id == "" {
		return c
	}
	ctx, cancel := context.WithTimeout(l.ctx, 30*time.Second)
	defer cancel()
	c, err := cli.GetConversation(ctx, id)
	if err != nil || c == nil {
		l.log.Warn().AnErr("error", err).Msg("conversation details not fetched")
		return nil
	}
	l.noteConv(c)
	return c
}

var skipIn = map[gmproto.MessageStatusType]bool{
	gmproto.MessageStatusType_INCOMING_AUTO_DOWNLOADING:       true,
	gmproto.MessageStatusType_INCOMING_RETRYING_AUTO_DOWNLOAD: true,
	gmproto.MessageStatusType_INCOMING_DELETED:                true,
}
var sentOut = map[gmproto.MessageStatusType]bool{
	gmproto.MessageStatusType_OUTGOING_COMPLETE:          true,
	gmproto.MessageStatusType_OUTGOING_DELIVERED:         true,
	gmproto.MessageStatusType_OUTGOING_DISPLAYED:         true,
	gmproto.MessageStatusType_OUTGOING_NOT_DELIVERED_YET: true,
}

type person struct {
	Number string `json:"number"`
	Name   string `json:"name"`
}

func number(p *gmproto.Participant) string {
	if n := p.GetID().GetNumber(); n != "" {
		return n
	}
	return p.GetFormattedNumber()
}

// row turns one message into what the server stores; ok is false for what is not a finished text (a send still under
// way, a download still running, a group notice, a deleted one).
func (l *link) row(m *libgm.WrappedMessage, c *gmproto.Conversation) (map[string]any, string) {
	st := m.GetMessageStatus().GetStatus()
	l.mu.Lock()
	self := m.GetParticipantID() == "1" || contains(l.st.SelfIDs, m.GetParticipantID())
	l.mu.Unlock()
	var direction string
	switch {
	case st >= 200 || st == gmproto.MessageStatusType_STATUS_UNKNOWN:
		return nil, "a notice, not a text"
	case st < 100:
		if !sentOut[st] {
			return nil, "not sent yet"
		}
		direction = "out"
	default:
		if skipIn[st] {
			return nil, "still downloading on the phone"
		}
		direction = "in"
		if self {
			direction = "out"
		}
	}
	var text []string
	var media []map[string]any
	pending, thumb := false, false
	for i, info := range m.GetMessageInfo() {
		if mc := info.GetMessageContent(); mc != nil && strings.TrimSpace(mc.GetContent()) != "" {
			text = append(text, mc.GetContent())
		}
		if md := mediaOf(info); md != nil {
			if hasMedia(md) {
				media = append(media, l.download(m, i, md))
				if md.GetMediaID() == "" {
					// as the bridge does (convertGoogleMedia's isThumbnail, then requestFullMedia): only the thumbnail can be had, so the
					// phone is asked for the full size; it comes as a later event of the same text with its media id, handed over again
					thumb = true
					l.askFull(m, info.GetActionMessageID())
				}
			} else {
				// as the bridge does ("Waiting for attachment"): no media id and no thumbnail id is a picture still coming, whatever
				// small preview is sent inline; the text is handed over now and again, onto the same stored text, when its picture comes
				pending = true
				l.log.Info().Str("conversation", m.GetConversationID()).Str("msg_id", m.GetMessageID()).
					Str("sent", time.UnixMicro(m.GetTimestamp()).Format("2006-01-02 15:04:05")).Bool("old", m.IsOld).Int("part", i).
					Str("mime", md.GetMimeType()).Int("inline_bytes", len(md.GetMediaData())).Str("status", st.String()).
					Str("result", "not ready: no media id or thumbnail id yet").Msg("picture seen")
			}
		}
	}
	if len(text) == 0 && len(media) == 0 && !pending {
		return nil, "no words and no picture"
	}
	var others []person
	sender := person{}
	group := false
	name := ""
	if c != nil {
		name = c.GetName()
		group = c.GetIsGroupChat() || len(c.GetOtherParticipants()) > 1
		for _, p := range c.GetParticipants() {
			if p.GetIsMe() {
				continue
			}
			pp := person{Number: number(p), Name: p.GetFullName()}
			if p.GetIsVisible() {
				others = append(others, pp) // Google's fake participant is not one of the people (the bridge ignores it)
			}
			if p.GetID().GetParticipantID() == m.GetParticipantID() {
				sender = pp
			}
		}
	}
	if sender.Number == "" && direction == "in" && m.GetSenderParticipant() != nil {
		sender = person{Number: number(m.GetSenderParticipant()), Name: m.GetSenderParticipant().GetFullName()}
	}
	media = compact(media)
	return map[string]any{
		"conv": m.GetConversationID(), "id": m.GetMessageID(), "ts_us": m.GetTimestamp(), "direction": direction,
		"text": strings.Join(text, "\n"), "group": group, "conv_name": name, "sender": sender, "others": others,
		"media": media, "is_old": m.IsOld, "tmp_id": m.GetTmpID(), "status": st.String(), "pending": pending,
		"thumbnail": thumb,
	}, ""
}

func compact(in []map[string]any) []map[string]any {
	out := []map[string]any{}
	for _, m := range in {
		if m != nil {
			out = append(out, m)
		}
	}
	return out
}

var unsafeName = regexp.MustCompile(`[^A-Za-z0-9._-]+`)

// download fetches one picture or file into the media folder; the server takes it from there and removes it.
func (l *link) download(m *libgm.WrappedMessage, n int, md *gmproto.MediaContent) map[string]any {
	msgID := m.GetMessageID()
	l.mu.Lock()
	cli := l.cli
	l.mu.Unlock()
	// every picture or file seen is said in the log: which of its three sources it has, and how the download went
	seen := l.log.Info().Str("conversation", m.GetConversationID()).Str("msg_id", msgID).Str("sent", time.UnixMicro(m.GetTimestamp()).Format("2006-01-02 15:04:05")).
		Bool("old", m.IsOld).Int("part", n).Str("mime", md.GetMimeType()).Bool("media_id", md.GetMediaID() != "").
		Bool("thumbnail_id", md.GetThumbnailMediaID() != "").Int("inline_bytes", len(md.GetMediaData()))
	full := md.GetMediaID() != "" // the picture at its full size, not its thumbnail
	if cli == nil || l.test {
		seen.Str("result", "not downloaded: not connected").Msg("picture seen")
		return map[string]any{"name": md.GetMediaName(), "mime": md.GetMimeType(), "path": "", "full": full}
	}
	ctx, cancel := context.WithTimeout(l.ctx, 2*time.Minute)
	defer cancel()
	var body io.ReadCloser
	var err error
	switch { // as the bridge does: the media id, else the thumbnail's (row() hands over no picture with neither)
	case md.GetMediaID() != "":
		body, err = cli.DownloadMedia(ctx, md.GetMediaID(), md.GetDecryptionKey())
	default:
		body, err = cli.DownloadMedia(ctx, md.GetThumbnailMediaID(), md.GetThumbnailDecryptionKey())
	}
	if err != nil {
		seen.Str("result", "not downloaded: "+short(err)).Msg("picture seen")
		return map[string]any{"name": md.GetMediaName(), "mime": md.GetMimeType(), "path": "", "error": short(err), "full": full}
	}
	defer body.Close()
	ext := filepath.Ext(md.GetMediaName())
	if ext == "" {
		if exts, _ := mime.ExtensionsByType(md.GetMimeType()); len(exts) > 0 {
			ext = exts[0]
		}
	}
	_ = os.MkdirAll(l.mediaDir, 0o700)
	which := "" // the full picture has its own file: the thumbnail's may still be waiting to be stored when the full one comes
	if full {
		which = "_full"
	}
	path := filepath.Join(l.mediaDir, unsafeName.ReplaceAllString(fmt.Sprintf("%s_%d%s", msgID, n, which), "_")+ext)
	f, err := os.Create(path)
	var size int64
	if err == nil {
		size, err = io.Copy(f, io.LimitReader(body, 100<<20))
		f.Close()
	}
	if err != nil {
		_ = os.Remove(path)
		seen.Str("result", "not saved: "+short(err)).Msg("picture seen")
		return map[string]any{"name": md.GetMediaName(), "mime": md.GetMimeType(), "path": "", "error": short(err), "full": full}
	}
	seen.Str("result", "downloaded").Int64("bytes", size).Bool("full_size", full).Msg("picture seen")
	return map[string]any{"name": md.GetMediaName(), "mime": md.GetMimeType(), "path": path, "full": full}
}

// askFull asks the phone for a picture's full size, as the bridge's requestFullMedia does (GetFullSizeImage with the
// message id and the picture's part id): once per picture while this program runs, away from the caller (a catch-up calls
// this inline). The answer is empty; the full picture comes as a later event of the same text, carrying its media id.
func (l *link) askFull(m *libgm.WrappedMessage, part string) {
	ev := l.log.Info().Str("conversation", m.GetConversationID()).Str("msg_id", m.GetMessageID()).Str("part_id", part)
	if part == "" {
		ev.Str("result", "not asked: no part id").Msg("full size")
		return
	}
	key := m.GetMessageID() + "|" + part
	l.mu.Lock()
	cli, asked := l.cli, l.fullAsked[key]
	if !asked {
		if len(l.fullAsked) > 50000 {
			l.fullAsked = map[string]bool{}
		}
		l.fullAsked[key] = true
	}
	l.mu.Unlock()
	if asked {
		ev.Str("result", "not asked again").Msg("full size")
		return
	}
	if cli == nil || l.test {
		ev.Str("result", "asked (not sent: not connected)").Msg("full size")
		return
	}
	go func() {
		ctx, cancel := context.WithTimeout(l.ctx, time.Minute)
		defer cancel()
		if _, err := cli.GetFullSizeImage(ctx, m.GetMessageID(), part); err != nil {
			ev.Str("result", "ask failed: "+short(err)).Msg("full size")
			return
		}
		ev.Str("result", "asked").Msg("full size")
	}()
}

func (l *link) process(m *libgm.WrappedMessage) {
	// a conversation's switch to or from end-to-end encryption decides whether a text to it must be sent as RCS
	switch m.GetMessageStatus().GetStatus() {
	case gmproto.MessageStatusType_MESSAGE_STATUS_TOMBSTONE_PROTOCOL_SWITCH_RCS_TO_E2EE, gmproto.MessageStatusType_MESSAGE_STATUS_TOMBSTONE_PROTOCOL_SWITCH_TEXT_TO_E2EE:
		l.mu.Lock()
		l.st.ForceRCS[m.GetConversationID()] = true
		l.mu.Unlock()
		go l.save()
	case gmproto.MessageStatusType_MESSAGE_STATUS_TOMBSTONE_PROTOCOL_SWITCH_E2EE_TO_RCS, gmproto.MessageStatusType_MESSAGE_STATUS_TOMBSTONE_PROTOCOL_SWITCH_E2EE_TO_TEXT:
		l.mu.Lock()
		delete(l.st.ForceRCS, m.GetConversationID())
		l.mu.Unlock()
		go l.save()
	}
	key := m.GetMessageID()
	if key == "" {
		l.drop(m, "no message id")
		return
	}
	l.mu.Lock()
	done := l.seen[key]
	l.mu.Unlock()
	// the same text comes again with each change of its status; as the bridge edits a message when its picture arrives (and when a
	// thumbnail's media id becomes the full picture's, MessageWasEdited), a text handed over before its picture was ready, or with
	// its picture at thumbnail size, is handed over again with the picture, then with the full one
	if done == 3 || (done == 2 && !mediaFull(m)) || (done == 1 && !mediaReady(m)) {
		l.drop(m, "already handed over")
		return
	}
	r, why := l.row(m, l.conv(m.GetConversationID()))
	if why != "" {
		l.drop(m, why)
		return
	}
	state := 3
	if pending, _ := r["pending"].(bool); pending {
		state = 1
	} else if thumb, _ := r["thumbnail"].(bool); thumb {
		state = 2
	}
	l.mu.Lock()
	if len(l.seen) > 50000 {
		l.seen = map[string]int{}
	}
	l.seen[key] = state
	l.mu.Unlock()
	emit(map[string]any{"type": "message", "row": r})
}

// drop says in the link's log that a message event was not handed over, and why, so none goes unseen.
func (l *link) drop(m *libgm.WrappedMessage, why string) {
	n, ready, full := 0, 0, 0
	for _, info := range m.GetMessageInfo() {
		if md := mediaOf(info); md != nil {
			n++
			if hasMedia(md) {
				ready++
			}
			if md.GetMediaID() != "" {
				full++
			}
		}
	}
	l.log.Info().Str("why", why).Str("status", m.GetMessageStatus().GetStatus().String()).Str("conversation", m.GetConversationID()).
		Str("msg_id", m.GetMessageID()).Int("pictures", n).Int("pictures_ready", ready).Int("with_media_id", full).Bool("old", m.IsOld).Msg("message not handed over")
}

func mediaOf(info *gmproto.MessageInfo) *gmproto.MediaContent {
	md := info.GetMediaContent()
	if md == nil && info.GetLocationContent() != nil {
		md = info.GetLocationContent().GetMediaContent()
	}
	return md
}

// hasMedia: the picture or file can be had, as the bridge takes it (hasInProgressMedia): its media id, else its thumbnail's.
// The few hundred bytes some updates carry inline are only a preview sent while the phone still downloads the picture.
func hasMedia(md *gmproto.MediaContent) bool {
	return md.GetMediaID() != "" || md.GetThumbnailMediaID() != ""
}

// mediaReady: every picture of the message can be had (the bridge's !hasInProgressMedia), so a text handed over before
// its pictures were ready is handed over again with them.
func mediaReady(m *libgm.WrappedMessage) bool {
	for _, info := range m.GetMessageInfo() {
		if md := mediaOf(info); md != nil && !hasMedia(md) {
			return false
		}
	}
	return true
}

// mediaFull: every picture of the message has its media id (its full size), so a text handed over with a thumbnail is handed
// over again once with the full picture.
func mediaFull(m *libgm.WrappedMessage) bool {
	for _, info := range m.GetMessageInfo() {
		if md := mediaOf(info); md != nil && md.GetMediaID() == "" {
			return false
		}
	}
	return true
}

// catchUp reads the newest conversations and hands over what is newer than the last text known; no deep history.
// Returns true when there was a gap (something newer than the last data received).
func (l *link) catchUp(anchor time.Time) bool {
	l.mu.Lock()
	cli := l.cli
	if cli == nil || l.catching {
		l.mu.Unlock()
		return false
	}
	l.catching = true
	since := maxTime(anchor, l.since)
	l.mu.Unlock()
	defer func() { l.mu.Lock(); l.catching = false; l.mu.Unlock() }()
	floor := time.Now().Add(-7 * 24 * time.Hour)
	if since.IsZero() {
		since = time.Now().Add(-24 * time.Hour)
	} else if since.Before(floor) {
		since = floor
	}
	ctx, cancel := context.WithTimeout(l.ctx, 5*time.Minute)
	defer cancel()
	// every conversation with a text since then: the list is read a page at a time (newest first) until a page ends before it
	var convs []*gmproto.Conversation
	var cursor *gmproto.Cursor
	for page := 0; page < 20; page++ {
		pctx, done := context.WithTimeout(ctx, time.Minute)
		resp, err := cli.ListConversations(pctx, &gmproto.ListConversationsRequest{Count: 25, Folder: gmproto.ListConversationsRequest_INBOX, Cursor: cursor})
		done()
		if err != nil {
			if len(convs) == 0 {
				l.log.Warn().Err(err).Msg("catch-up: conversation list not read")
				return false
			}
			l.log.Warn().Err(err).Int("pages", page).Msg("catch-up: a later page of the conversation list was not read")
			break
		}
		cs := resp.GetConversations()
		convs = append(convs, cs...)
		if len(cs) == 0 || !time.UnixMicro(cs[len(cs)-1].GetLastMessageTimestamp()).After(since) {
			break
		}
		last := cs[len(cs)-1]
		if next := resp.GetCursor(); next != nil && next.GetLastItemID() != "" {
			cursor = next
		} else {
			cursor = &gmproto.Cursor{LastItemID: last.GetConversationID(), LastItemTimestamp: time.UnixMicro(last.GetLastMessageTimestamp()).UnixMilli()}
		}
	}
	gap, n := false, 0
	emit(map[string]any{"type": "convs", "convs": convList(convs)}) // the server matches its older conversations to these
	for _, c := range convs {
		l.noteConv(c)
		if !time.UnixMicro(c.GetLastMessageTimestamp()).After(since) {
			continue
		}
		gap = true
		var cursor *gmproto.Cursor
		for page := 0; page < 4; page++ {
			mr, err := cli.FetchMessages(ctx, c.GetConversationID(), 25, cursor)
			if err != nil {
				l.log.Warn().Err(err).Msg("catch-up: messages not read")
				break
			}
			older := false
			for _, m := range mr.GetMessages() {
				if time.UnixMicro(m.GetTimestamp()).After(since) {
					l.process(&libgm.WrappedMessage{Message: m, IsOld: true})
					n++
				} else {
					older = true
				}
			}
			cursor = mr.GetCursor()
			if older || cursor == nil || len(mr.GetMessages()) == 0 {
				break
			}
		}
	}
	l.log.Info().Int("texts", n).Bool("gap", gap).Int("conversations", len(convs)).Str("since", since.Format("2006-01-02 15:04")).Msg("catch-up done")
	return gap
}

// convList is what the server needs of each conversation to match the ones it stored before the link: the id, the name,
// whether it is a group, and the other people's numbers and names. As the bridge's chat info does: a group is what Google
// marks as one, and a participant that is me or not visible (Google's fake participant) is not one of the other people.
func convList(cs []*gmproto.Conversation) []map[string]any {
	out := []map[string]any{}
	for _, c := range cs {
		others := []person{}
		for _, p := range c.GetParticipants() {
			if !p.GetIsMe() && p.GetIsVisible() {
				others = append(others, person{Number: number(p), Name: p.GetFullName()})
			}
		}
		out = append(out, map[string]any{"id": c.GetConversationID(), "name": c.GetName(),
			"group": c.GetIsGroupChat(), "others": others, "last": c.GetLastMessageTimestamp()})
	}
	return out
}

// listConvs reads the whole conversation list (inbox, then archive) and notes each one for sending. Google answers a page at
// a time and often gives no cursor; then the cursor is made from the page's last item, as the bridge's backfill does for
// messages (its id and time in milliseconds; microseconds are tried once if Google gives the same page back).
func (l *link) listConvs() ([]*gmproto.Conversation, error) {
	l.mu.Lock()
	cli := l.cli
	l.mu.Unlock()
	if cli == nil {
		return nil, errors.New("not connected")
	}
	// each page has its own time (the list of a phone with years of texts takes many pages); the whole read has a ceiling
	whole, cancel := context.WithTimeout(l.ctx, 14*time.Minute)
	defer cancel()
	var all []*gmproto.Conversation
	seen := map[string]bool{}
	for _, folder := range []gmproto.ListConversationsRequest_Folder{gmproto.ListConversationsRequest_INBOX, gmproto.ListConversationsRequest_ARCHIVE} {
		var cursor *gmproto.Cursor
		micro := false
		pages, got := 0, 0
		for pages < 60 {
			ctx, done := context.WithTimeout(whole, time.Minute)
			resp, err := cli.ListConversations(ctx, &gmproto.ListConversationsRequest{Count: 75, Folder: folder, Cursor: cursor})
			done()
			pages++
			if err != nil {
				l.log.Warn().Err(err).Int("pages", pages).Msg("conversation list: a page was not read")
				if len(all) > 0 {
					break
				}
				return nil, err
			}
			cs := resp.GetConversations()
			fresh := 0
			for _, c := range cs {
				if !seen[c.GetConversationID()] {
					seen[c.GetConversationID()] = true
					all = append(all, c)
					l.noteConv(c)
					fresh++
				}
			}
			got += fresh
			if len(cs) == 0 {
				break
			}
			if fresh == 0 {
				if cursor == nil || resp.GetCursor() != nil || micro {
					break
				}
				micro = true // the same page again: Google wants the time in microseconds
			}
			last := cs[len(cs)-1]
			if next := resp.GetCursor(); next != nil && next.GetLastItemID() != "" {
				cursor = next
			} else if micro {
				cursor = &gmproto.Cursor{LastItemID: last.GetConversationID(), LastItemTimestamp: last.GetLastMessageTimestamp()}
			} else {
				cursor = &gmproto.Cursor{LastItemID: last.GetConversationID(), LastItemTimestamp: time.UnixMicro(last.GetLastMessageTimestamp()).UnixMilli()}
			}
		}
		l.log.Info().Str("folder", folder.String()).Int("pages", pages).Int("conversations", got).Msg("conversation list read")
	}
	return all, nil
}

// ---------------------------------------------------------------------------------------------------------------
// sending

// buildSend forms the request exactly as the bridge's ConvertMatrixMessage does for a plain text.
func buildSend(c *gmproto.Conversation, text, tmpID string, sim *gmproto.SIMCard, forceRCS bool) *gmproto.SendMessageRequest {
	id := c.GetConversationID()
	return &gmproto.SendMessageRequest{
		ConversationID: id,
		MessagePayload: &gmproto.MessagePayload{
			TmpID:          tmpID,
			ConversationID: id,
			ParticipantID:  c.GetDefaultOutgoingID(),
			TmpID2:         tmpID,
			MessageInfo: []*gmproto.MessageInfo{{
				Data: &gmproto.MessageInfo_MessageContent{MessageContent: &gmproto.MessageContent{Content: text}},
			}},
		},
		SIMPayload: sim.GetSIMData().GetSIMPayload(),
		TmpID:      tmpID,
		ForceRCS: c.GetType() == gmproto.ConversationType_RCS &&
			c.GetSendMode() == gmproto.ConversationSendMode_SEND_MODE_AUTO && forceRCS,
	}
}

func (l *link) request(c *gmproto.Conversation, text, tmp string) *gmproto.SendMessageRequest {
	l.mu.Lock()
	sim := l.sims[c.GetDefaultOutgoingID()]
	force := l.st.ForceRCS[c.GetConversationID()]
	l.mu.Unlock()
	if sim == nil {
		sim = c.GetSimCard()
	}
	if tmp == "" {
		tmp = util.GenerateTmpID()
	}
	return buildSend(c, text, tmp, sim, force)
}

var sendBackoff = []time.Duration{3 * time.Second, 8 * time.Second, 20 * time.Second}

func transient(s gmproto.SendMessageResponse_Status) bool {
	return s == gmproto.SendMessageResponse_FAILURE_2 || s == gmproto.SendMessageResponse_FAILURE_3
}

func (l *link) send(rid string, cmd map[string]any) {
	l.mu.Lock()
	cli, state := l.cli, l.state
	l.mu.Unlock()
	text := str(cmd["text"])
	if cli == nil {
		reply(rid, map[string]any{"ok": false, "error": "Google Messages is not connected on this computer."})
		return
	}
	if strings.TrimSpace(text) == "" {
		reply(rid, map[string]any{"ok": false, "error": "There is nothing to send."})
		return
	}
	ctx, cancel := context.WithTimeout(l.ctx, 90*time.Second)
	defer cancel()
	var c *gmproto.Conversation
	if id := str(cmd["conv"]); id != "" {
		c = l.conv(id)
	}
	if c == nil {
		phone := str(cmd["phone"])
		if phone == "" {
			reply(rid, map[string]any{"ok": false, "error": "That conversation could not be found in Google Messages."})
			return
		}
		resp, err := cli.GetOrCreateConversation(ctx, &gmproto.GetOrCreateConversationRequest{
			Numbers: []*gmproto.ContactNumber{{MysteriousInt: 2, Number: phone, Number2: phone}},
		})
		if err != nil || resp.GetConversation().GetConversationID() == "" {
			reply(rid, map[string]any{"ok": false, "error": "Google Messages could not open a conversation with " + phone + "."})
			return
		}
		c = resp.GetConversation()
		l.noteConv(c)
	}
	req := l.request(c, text, str(cmd["tmp"]))
	resp, err := cli.SendMessage(ctx, req)
	for i := 0; err == nil && transient(resp.GetStatus()) && i < len(sendBackoff); i++ {
		select {
		case <-ctx.Done():
			err = ctx.Err()
		case <-time.After(sendBackoff[i]):
			resp, err = cli.SendMessage(ctx, req)
		}
	}
	switch {
	case err != nil && (errors.Is(err, libgm.ErrPhoneNotResponding) || errors.Is(err, context.DeadlineExceeded)):
		reply(rid, map[string]any{"ok": false, "unsure": true, "conv": c.GetConversationID(),
			"error": "Your phone did not answer, so it is not known whether the text went. It may still go when the phone is back. Look on your phone before you send it again."})
	case err != nil:
		reply(rid, map[string]any{"ok": false, "conv": c.GetConversationID(), "error": "Google Messages did not take it (" + short(err) + ")."})
	case resp.GetStatus() != gmproto.SendMessageResponse_SUCCESS:
		why := "Your phone did not send it (" + resp.GetStatus().String() + ")."
		l.mu.Lock()
		nosim := len(l.sims) == 0
		l.mu.Unlock()
		if resp.GetStatus() == gmproto.SendMessageResponse_FAILURE_2 && nosim {
			why = "Your phone has no SIM card Google Messages can send from."
		}
		reply(rid, map[string]any{"ok": false, "conv": c.GetConversationID(), "error": why})
	default:
		reply(rid, map[string]any{"ok": true, "conv": c.GetConversationID(), "tmp": req.GetTmpID(), "state": state})
	}
}

// ---------------------------------------------------------------------------------------------------------------
// signing in with Google-account cookies, then the emoji on the phone

var wanted = []string{"SID", "HSID", "OSID", "SSID", "APISID", "SAPISID", "__Secure-1PSIDTS"}
var required = []string{"SID", "HSID", "OSID", "SSID", "APISID", "SAPISID"}

func pairError(err error) string {
	switch {
	case errors.Is(err, libgm.ErrNoDevicesFound):
		return "Google found no phone with Google Messages on this Google account. On your phone, open Messages, tap your picture, then Device pairing, and check it uses the same Google account."
	case errors.Is(err, libgm.ErrPhoneNotFound), errors.Is(err, libgm.ErrPhoneInactive):
		return "Google could not reach Messages on your phone. Open Messages on your phone, then sign in here again."
	case errors.Is(err, libgm.ErrPairingInitTimeout):
		return "Your phone did not answer. Open Messages on your phone, then sign in here again."
	case errors.Is(err, events.ErrCallerNoPermission):
		return "Google refused this sign-in. Sign in again in a new private window and copy the cookies again."
	case errors.Is(err, libgm.ErrIncorrectEmoji):
		return "A different emoji was tapped on your phone. Sign in again to get a new one."
	case errors.Is(err, libgm.ErrPairingCancelled):
		return "Pairing was cancelled on your phone."
	case errors.Is(err, libgm.ErrPairingTimeout):
		return "No emoji was tapped on your phone in time. Sign in again to get a new one."
	}
	return "Google did not accept the sign-in (" + short(err) + "). Sign in again in a new private window and copy the cookies again."
}

func (l *link) pair(rid string, cmd map[string]any) {
	given, _ := cmd["cookies"].(map[string]any)
	cookies := map[string]string{}
	for _, k := range wanted {
		if v := strings.TrimSpace(str(given[k])); v != "" {
			cookies[k] = v
		}
	}
	var missing []string
	for _, k := range required {
		if cookies[k] == "" {
			missing = append(missing, k)
		}
	}
	if len(missing) > 0 {
		reply(rid, map[string]any{"ok": false, "error": "These cookies are missing: " + strings.Join(missing, ", ") + "."})
		return
	}
	l.cancelPair()
	ad := libgm.NewAuthData()
	ad.Cookies = cookies
	cli := libgm.NewClient(ad, nil, l.log.With().Str("part", "libgm pairing").Logger(), exhttp.SensibleClientSettings)
	cli.SetEventHandler(func(evt any) { l.log.Debug().Type("event", evt).Msg("event while pairing") })
	ctx, cancel := context.WithTimeout(l.ctx, 60*time.Second)
	defer cancel()
	if err := cli.FetchConfig(ctx); err != nil {
		reply(rid, map[string]any{"ok": false, "error": "Google did not accept those cookies (" + short(err) + "). Sign in again in a new private window and copy them again."})
		return
	}
	bg, stop := context.WithCancel(l.ctx)
	emoji, sess, err := cli.StartGaiaPairing(ctx, bg)
	if err != nil {
		stop()
		cli.Disconnect()
		reply(rid, map[string]any{"ok": false, "error": pairError(err)})
		return
	}
	l.mu.Lock()
	l.pairCli, l.pairStop, l.emoji = cli, stop, emoji
	l.mu.Unlock()
	l.setState("pairing", "Tap the matching emoji in Google Messages on your phone.")
	reply(rid, map[string]any{"ok": true, "emoji": emoji})
	go func() {
		defer stop()
		_, err := cli.FinishGaiaPairing(bg, sess)
		l.mu.Lock()
		mine := l.pairCli == cli
		if mine {
			l.pairCli, l.pairStop, l.emoji = nil, nil, ""
		}
		l.mu.Unlock()
		if !mine {
			return
		}
		cli.Disconnect()
		if err != nil {
			emit(map[string]any{"type": "pair_done", "ok": false, "error": pairError(err)})
			l.connectOrSignedOut()
			return
		}
		// paired: the new sign-in replaces the old one, and the link connects with a fresh client, as the bridge's finishLogin does
		l.mu.Lock()
		old := l.cli
		l.cli = nil
		l.st.Auth, l.st.Signed = cli.AuthData, true
		l.mu.Unlock()
		if old != nil {
			old.SetEventHandler(func(any) {})
			old.Disconnect()
		}
		l.save()
		emit(map[string]any{"type": "pair_done", "ok": true})
		go l.connect()
	}()
}

func (l *link) connectOrSignedOut() {
	l.mu.Lock()
	cli := l.cli
	l.mu.Unlock()
	if cli == nil {
		go l.connect()
	} else if cli.IsConnected() {
		l.setState("connected", "")
	}
}

func (l *link) cancelPair() {
	l.mu.Lock()
	stop, cli := l.pairStop, l.pairCli
	l.pairCli, l.pairStop, l.emoji = nil, nil, ""
	l.mu.Unlock()
	if stop != nil {
		stop()
	}
	if cli != nil {
		cli.Disconnect()
	}
}

// ---------------------------------------------------------------------------------------------------------------
// commands from the server

func (l *link) command(line []byte) {
	var cmd map[string]any
	if json.Unmarshal(line, &cmd) != nil {
		return
	}
	rid := str(cmd["rid"])
	switch str(cmd["cmd"]) {
	case "since":
		if us, ok := cmd["us"].(float64); ok && us > 0 {
			l.mu.Lock()
			l.since = time.UnixMicro(int64(us))
			l.mu.Unlock()
		}
	case "browser":
		l.mu.Lock()
		l.yield = str(cmd["mode"]) == "yield"
		yield, inactive := l.yield, l.inactive
		l.mu.Unlock()
		if !yield && inactive {
			l.setState("connecting", "Google Messages was opened somewhere else; taking it back.")
			go l.aggressiveSetActive()
		}
	case "take_back":
		go func() {
			l.mu.Lock()
			cli, inactive := l.cli, l.inactive
			l.mu.Unlock()
			if cli == nil {
				reply(rid, map[string]any{"ok": false, "error": "not connected"})
				return
			}
			if !inactive {
				reply(rid, map[string]any{"ok": true, "taken": false})
				return
			}
			l.setState("connecting", "Taking Google Messages back from the browser.")
			if err := cli.SetActiveSession(l.ctx); err != nil {
				l.log.Warn().Err(err).Msg("could not take the session back")
				l.setState("browser_open", "Paused while Messages is open in your browser.")
				reply(rid, map[string]any{"ok": false, "error": err.Error()})
				return
			}
			reply(rid, map[string]any{"ok": true, "taken": true}) // Google's BROWSER_ACTIVE then marks it connected and catches up
		}()
	case "status":
		m := l.statusMap("reply")
		m["rid"] = rid
		emit(m)
	case "pair":
		go l.pair(rid, cmd)
	case "cancel_pair":
		l.cancelPair()
		l.connectOrSignedOut()
		reply(rid, map[string]any{"ok": true})
	case "send":
		go l.send(rid, cmd)
	case "catchup":
		go func() { gap := l.catchUp(time.Time{}); reply(rid, map[string]any{"ok": true, "gap": gap}) }()
	case "convs":
		go func() {
			cs, err := l.listConvs()
			if err != nil {
				reply(rid, map[string]any{"ok": false, "error": short(err)})
				return
			}
			reply(rid, map[string]any{"ok": true, "convs": convList(cs)})
		}()
	case "fake":
		if !l.test {
			reply(rid, map[string]any{"ok": false})
			return
		}
		var c gmproto.Conversation
		var m gmproto.Message
		cj, _ := json.Marshal(cmd["conv"])
		mj, _ := json.Marshal(cmd["msg"])
		if protojson.Unmarshal(cj, &c) != nil || protojson.Unmarshal(mj, &m) != nil {
			reply(rid, map[string]any{"ok": false, "error": "bad fake"})
			return
		}
		old, _ := cmd["is_old"].(bool)
		l.handle(&c)
		l.handle(&libgm.WrappedMessage{Message: &m, IsOld: old})
		reply(rid, map[string]any{"ok": true})
	case "form_send":
		if !l.test {
			reply(rid, map[string]any{"ok": false})
			return
		}
		c := l.conv(str(cmd["conv"]))
		if c == nil {
			reply(rid, map[string]any{"ok": false, "error": "no such conversation"})
			return
		}
		raw, _ := protojson.Marshal(l.request(c, str(cmd["text"]), str(cmd["tmp"])))
		reply(rid, map[string]any{"ok": true, "request": json.RawMessage(raw)})
	default:
		reply(rid, map[string]any{"ok": false, "error": "unknown command"})
	}
}

// ---------------------------------------------------------------------------------------------------------------

func str(v any) string {
	s, _ := v.(string)
	return s
}

func short(err error) string {
	s := err.Error()
	if len(s) > 160 {
		s = s[:160]
	}
	return s
}

func contains(list []string, s string) bool {
	for _, x := range list {
		if x == s {
			return true
		}
	}
	return false
}

func maxTime(a, b time.Time) time.Time {
	if a.After(b) {
		return a
	}
	return b
}

func main() {
	authPath := flag.String("auth", "", "the file that keeps the sign-in")
	mediaDir := flag.String("media", "", "the folder for pictures and files of received texts")
	test := flag.Bool("test", false, "no connection to Google; fake events only")
	flag.Parse()
	if *authPath == "" && !*test {
		fmt.Fprintln(os.Stderr, "messages-link: --auth is required")
		os.Exit(2)
	}
	ctx, cancel := context.WithCancel(context.Background())
	logger := zerolog.New(zerolog.ConsoleWriter{Out: os.Stderr, NoColor: true, TimeFormat: "2006-01-02 15:04:05"}).
		With().Timestamp().Logger().Level(zerolog.InfoLevel)
	l := &link{path: *authPath, mediaDir: *mediaDir, test: *test, log: logger, ctx: ctx, responding: true,
		convs: map[string]*gmproto.Conversation{}, seen: map[string]int{}, fullAsked: map[string]bool{}, queue: make(chan *libgm.WrappedMessage, 256)}
	if *test {
		l.st.ForceRCS, l.sims = map[string]bool{}, map[string]*gmproto.SIMCard{}
		l.state = "test"
	} else {
		l.load()
		go l.connect()
	}
	go l.messages()
	in := bufio.NewScanner(os.Stdin)
	in.Buffer(make([]byte, 64*1024), 4<<20)
	for in.Scan() {
		l.command(append([]byte(nil), in.Bytes()...))
	}
	// the input closed: the server stopped. Save, disconnect, end.
	if *test {
		time.Sleep(300 * time.Millisecond) // the fake messages still being handed over finish
	}
	l.cancelPair()
	l.mu.Lock()
	cli := l.cli
	l.mu.Unlock()
	l.save()
	if cli != nil {
		cli.Disconnect()
	}
	cancel()
}
