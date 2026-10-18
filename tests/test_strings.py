"""Translations: every key exists, fa/en placeholders match, HTML is well formed, no leftover branding."""

import re

import pytest

from locales.strings import S, t
from tests import scan_strings
from tests.fake_telegram import check_html


def test_every_used_key_exists_and_placeholders_line_up(capsys):
    used, dyn = scan_strings.collect()
    problems = []
    for key, calls in used.items():
        if key not in S:
            problems.append(f"missing key {key} ({calls[0][1]})")
            continue
        for idx, lang in enumerate(("fa", "en")):
            ph = set(re.findall(r"\{(\w+)\}", S[key][idx]))
            for kws, fname in calls:
                if ph - kws:
                    problems.append(f"{key}[{lang}] needs {sorted(ph - kws)} ({fname})")
    for prefix in dyn:
        if not any(k.startswith(prefix) for k in S):
            problems.append(f"missing dynamic prefix {prefix}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("key", sorted(S))
def test_string_is_well_formed(key):
    fa, en = S[key]
    ph_fa, ph_en = set(re.findall(r"\{(\w+)\}", fa)), set(re.findall(r"\{(\w+)\}", en))
    assert ph_fa == ph_en, f"{key}: placeholder mismatch fa={ph_fa} en={ph_en}"
    for lang in ("fa", "en"):
        text = t(key, lang, **{p: "x" for p in ph_fa})
        assert "%BRAND%" not in text
        if key.startswith("b_") or key.startswith(("f_", "aud_")):
            continue   # button labels are plain text, not HTML messages
        errors = check_html(text)
        assert not errors, f"{key}[{lang}]: {errors}"
