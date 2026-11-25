# Opening the page from anywhere, through Tailscale

For Claude: walk these steps one at a time. Each step ends with a mark in square brackets; never read the marks out. "docs" means Tailscale's own page (sources at the end), checked 11/16/26. Nobody checked these steps on a live screen yet.

To say first: "Tailscale is a free program (free for personal use) that gives this computer its own private, encrypted address, so you can open your page from your phone. Your page stays on this computer and stays locked with your password. You install it and sign in yourself; your assistant never does that for you."

1. Open tailscale.com/download/windows, click the download, run it, and sign in when it asks (with Google, Microsoft or another account). [docs: TS-install]
2. Tell me when Tailscale says it is connected. Claude runs `HELPER reach-status`; it says whether Tailscale is ready. [the assistant's own step: no outside screen]
3. Claude runs `HELPER reach-on`. The first time, your browser may open a Tailscale page asking you to approve turning on its sharing feature (called "Funnel") for this computer. Approve it there, then tell me, and Claude runs it again. [docs: TS-funnel]
4. Claude runs `HELPER reach-check` and gives you your page's address, starting https://. Send it to your phone, open it there, and sign in with your page's password. [the assistant's own step: no outside screen]

Good to know:
- The first time, the address can take up to 10 minutes to start working. Claude can check again.
- The page cannot be opened while this computer is off, asleep or signed out. Nothing is lost.
- If Tailscale is already used on this computer for something else, that is left as it is; the page takes a free spot, and its address may end in :8443 or :10000. [docs: TS-funnel, ports 443, 8443, 10000]
- Anyone with the address sees only the sign-in. Wrong passwords from outside are limited.

## If something goes wrong

- "Tailscale is not on this computer yet" or "not signed in": do step 1 again, then step 2.
- No free spot: Tailscale here already uses all three of its public spots for other things. The page stays on this computer only; say so.

## Sources

- TS-install: https://tailscale.com/download/windows and https://tailscale.com/kb/1347/installation (validated 12/19/25)
- TS-funnel: https://tailscale.com/kb/1223/funnel (validated 1/20/26)
