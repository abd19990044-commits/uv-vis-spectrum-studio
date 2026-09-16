from __future__ import annotations

import streamlit as st

from .chemometrics_ui_legacy import render_legacy_chemometrics
from .advanced_suite_ui import render_advanced_suite


def render_chemometrics(processed: list[dict]) -> None:
    render_legacy_chemometrics(processed)
    st.divider()
    render_advanced_suite(processed)
