"""A commit or merge runs only the tests for the files it changes, never the whole set.

The table below maps each part of the program to its test file(s). A changed file that matches no row runs no test.
    python githooks/run_matching_tests.py            (changed files = what is staged for this commit or merge)
    python githooks/run_matching_tests.py --list     (only say which tests would run)
"""
import fnmatch, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L = "engine/System/live/"
TIMEOUT = 120
MOST = 6        # more matched tests than this means the change is too wide for a commit check: the rest are named, not run

# part of the program (glob on the repo path) -> its test file(s) under tests/
TESTS = [
    (L + "chat.py", ["chat_full_acceptance.py", "one_brain_acceptance.py"]),
    (L + "picks.py", ["rebuild_picks_acceptance.py", "one_brain_acceptance.py"]),
    (L + "texts.py", ["texts_acceptance.py"]),
    (L + "textlink.py", ["texts_link_acceptance.py"]),
    (L + "messages_link/*", ["texts_link_acceptance.py"]),
    (L + "mail.py", ["mail_acceptance.py"]),
    (L + "mailpull.py", ["mail_sync_acceptance.py"]),
    (L + "mail_alerts.py", ["mail_alerts_acceptance.py"]),
    (L + "mail_cache.py", ["mail_cache_acceptance.py"]),
    (L + "mail_compose.py", ["mail_compose_acceptance.py"]),
    (L + "mail_handle.py", ["mail_handle_acceptance.py"]),
    (L + "mail_card.py", ["mail_card_acceptance.py"]),
    (L + "mail_rules.py", ["mail_rules_acceptance.py"]),
    (L + "mailhtml.py", ["mail_html_acceptance.py"]),
    (L + "invites.py", ["mail_invites_acceptance.py"]),
    (L + "mods.py", ["mods_acceptance.py"]),
    (L + "mod_checks.py", ["mod_checks_acceptance.py"]),
    (L + "test_cards.py", ["test_cards_acceptance.py"]),
    (L + "tools.py", ["tools_acceptance.py"]),
    (L + "project_tools.py", ["project_tools_acceptance.py"]),
    (L + "voice.py", ["voice_acceptance.py", "writing_acceptance.py"]),
    (L + "writing.py", ["writing_acceptance.py"]),
    (L + "people.py", ["contacts_acceptance.py"]),
    (L + "contact_strength.py", ["contacts_acceptance.py"]),
    (L + "items.py", ["cards_acceptance.py", "uncovered_verdict_acceptance.py"]),
    (L + "card.py", ["uncovered_verdict_acceptance.py", "rsi_signals_acceptance.py"]),
    (L + "held.py", ["uncovered_verdict_acceptance.py", "rsi_rows_acceptance.py"]),
    (L + "core/schema.sql", ["uncovered_verdict_acceptance.py"]),
    (L + "rule_book.py", ["rsi_rows_acceptance.py", "rsi_review_acceptance.py", "rsi_grader_acceptance.py"]),
    (L + "grader.py", ["rsi_grader_acceptance.py", "rsi_coach_acceptance.py", "rsi_levels_acceptance.py"]),
    (L + "coach.py", ["rsi_coach_acceptance.py", "rsi_loop_acceptance.py"]),
    (L + "rsi_loop.py", ["rsi_loop_acceptance.py", "rsi_guard_acceptance.py", "rebuild_levels_acceptance.py"]),
    (L + "levels.py", ["rebuild_levels_acceptance.py"]),
    (L + "work_rules.py", ["rebuild_levels_acceptance.py"]),
    (L + "send.py", ["rebuild_levels_acceptance.py", "send_shown_acceptance.py"]),
    (L + "rules/rulebook.json", ["guards_acceptance.py", "rebuild_levels_acceptance.py"]),
    (L + "wouldhide.py", ["rsi_guard_acceptance.py"]),
    (L + "changes_feed.py", ["rsi_guard_acceptance.py"]),
    (L + "start_fresh.py", ["start_fresh_acceptance.py", "rsi_defaults_acceptance.py"]),
    (L + "setup/setup_home.py", ["rsi_defaults_acceptance.py"]),
    (L + "core_rules/*", ["rsi_defaults_acceptance.py", "start_fresh_acceptance.py"]),
    (L + "starter/*", ["rsi_defaults_acceptance.py"]),
    (L + "rebuild.py", ["rsi_loop_acceptance.py"]),
    (L + "review.py", ["rsi_loop_acceptance.py"]),
    (L + "standing.py", ["rsi_loop_acceptance.py"]),
    (L + "filters.py", ["rsi_coach_acceptance.py"]),
    (L + "card_rules.py", ["card_rules_acceptance.py", "rsi_loop_acceptance.py"]),
    (L + "answers.py", ["card_rules_acceptance.py", "rsi_presses_acceptance.py", "rsi_rows_acceptance.py", "multi_answer_acceptance.py",
                        "card_answer_acts_acceptance.py"]),
    (L + "presses.py", ["card_rules_acceptance.py", "rsi_presses_acceptance.py", "rsi_loop_acceptance.py"]),
    (L + "think.py", ["cards_acceptance.py", "pass_time_acceptance.py", "judge_flow_acceptance.py", "describe_backlog_acceptance.py",
                      "uncovered_verdict_acceptance.py", "rsi_grader_acceptance.py", "one_brain_acceptance.py", "rebuild_picks_acceptance.py"]),
    (L + "card_search.py", ["one_brain_acceptance.py"]),
    (L + "core/judgment_payload.py", ["judge_flow_acceptance.py", "rsi_grader_acceptance.py"]),
    (L + "core/judgment_commit.py", ["judge_flow_acceptance.py", "uncovered_verdict_acceptance.py"]),
    (L + "db.py", ["judge_flow_acceptance.py"]),
    (L + "gather.py", ["describe_backlog_acceptance.py"]),
    (L + "ai_steps.py", ["describe_backlog_acceptance.py", "rsi_grader_acceptance.py"]),
    (L + "common.py", ["describe_backlog_acceptance.py"]),
    (L + "core/describe_images.py", ["describe_backlog_acceptance.py"]),
    (L + "limits.py", ["pass_time_acceptance.py"]),
    (L + "prompts/*", ["cards_acceptance.py"]),
    (L + "comeback.py", ["catch_up_acceptance.py", "rsi_loop_acceptance.py"]),
    (L + "core/rules.py", ["rules_and_mods_acceptance.py", "rsi_defaults_acceptance.py"]),
    (L + "core/inuse.py", ["rules_and_mods_acceptance.py"]),
    (L + "settings_*.py", ["layout_acceptance.py", "settings_acceptance.py", "calendar_settings_acceptance.py",
                           "rsi_review_acceptance.py", "rsi_levels_acceptance.py"]),
    (L + "calendar_view.py", ["calendar_acceptance.py"]),
    ("engine/System/live_page/vendor/*", ["calendar_acceptance.py"]),
    (L + "pass.py", ["pass_holds_acceptance.py"]),
    ("engine/System/live_page/listen.py", ["one_server_acceptance.py", "rsi_loop_acceptance.py"]),
    (L + "setup_steps.py", ["one_server_acceptance.py", "rsi_signals_acceptance.py"]),
    (L + "updates.py", ["update_guard_acceptance.py"]),
    ("engine/System/live_page/roadmaps.py", ["roadmap_connect_acceptance.py"]),
    ("engine/System/live_page/page.html", ["page_vision_acceptance.py", "roadmap_press_landed_acceptance.py", "calendar_settings_acceptance.py", "card_plan_page_acceptance.py", "handled_truth_acceptance.py",
                                           "rsi_review_acceptance.py", "rsi_levels_acceptance.py"]),
    ("scripts/assistant.py", ["update_guard_acceptance.py"]),
    ("scripts/roadmap_setup.py", ["roadmap_off_acceptance.py"]),
    ("scripts/questions_setup.py", ["questions_acceptance.py"]),
    ("scripts/hand_out.py", ["hand_out_acceptance.py"]),
    (L + "rules/rulebook.py", ["guards_acceptance.py"]),
    ("hooks/rulebook_guard.py", ["guards_acceptance.py"]),
    ("hooks/working_copy.py", ["working_copy_acceptance.py"]),
    (L + "replay*.py", ["replay_acceptance.py", "rsi_rows_acceptance.py"]),
    (L + "connections/_http.py", ["replay_acceptance.py"]),
    ("githooks/*", ["pointers_acceptance.py"]),
    ("tests/*_acceptance.py", None),          # a changed test file runs itself
]


def changed():
    out = subprocess.run(["git", "-C", ROOT, "diff", "--cached", "--name-only", "--diff-filter=ACMR"], capture_output=True, text=True).stdout
    return [l.strip() for l in out.splitlines() if l.strip()]


def wanted(files):
    want = []
    for f in files:
        for pat, tests in TESTS:
            if fnmatch.fnmatch(f, pat):
                for t in (tests if tests is not None else [os.path.basename(f)]):
                    if t not in want and os.path.isfile(os.path.join(ROOT, "tests", t)):
                        want.append(t)
    return want


def main():
    want = wanted(changed())
    if "--list" in sys.argv:
        print("\n".join(want) or "(no matching test)")
        return 0
    if not want:
        print("No test is mapped to the changed files: none run.")
        return 0
    run, skipped = want[:MOST], want[MOST:]
    for t in run:
        print("test:", t, flush=True)
        try:
            r = subprocess.run([sys.executable, os.path.join("tests", t)], cwd=ROOT, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"Refused: {t} ran longer than {TIMEOUT} seconds.", file=sys.stderr)
            return 1
        if r.returncode:
            print(f"Refused: {t} failed.", file=sys.stderr)
            return 1
    if skipped:
        print("Not run here (too many matched for one commit): " + ", ".join(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
