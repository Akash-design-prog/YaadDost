from app.llm import prompts

NOTES = "Deadlock: processes wait forever."


def system_text(language):
    return prompts.cards_messages(NOTES, 8, language)[0]["content"]


def test_rules_that_fixed_the_first_real_run_are_present():
    s = system_text("english")
    assert "ONLY facts present in the notes" in s
    assert "ONE card" in s and "fewer cards" in s      # no padding with near-duplicates
    assert "complete short sentence" in s              # no answer fragments
    assert "instructions in brackets" in s             # no leaked "(List the four conditions)"


def test_count_is_a_maximum_not_a_target():
    user = prompts.cards_messages(NOTES, 8, "english")[1]["content"]
    assert "at most 8" in user and NOTES in user


def test_language_style_is_applied():
    assert "Hinglish" in system_text("hinglish")
    assert "Hinglish" not in system_text("english")
    assert "simple English" in system_text("english")


def test_explain_messages_include_concept_and_notes():
    m = prompts.explain_messages("deadlock", NOTES, "hinglish")
    assert "deadlock" in m[1]["content"] and NOTES in m[1]["content"] and "Hinglish" in m[0]["content"]


def test_latex_is_forbidden_in_cards_and_explanations():
    assert "no LaTeX" in system_text("english")
    assert "no LaTeX" in prompts.explain_messages("x", "", "english")[0]["content"]
