from __future__ import annotations

import streamlit as st

from .advanced_suite_ui import render_advanced_suite
from .chemometrics_advanced_ui import render_advanced_chemometrics
from .chemometrics_basic_ui import render_basic_chemometrics


def render_chemometrics(processed: list[dict]) -> None:
    render_basic_chemometrics(processed)
    st.divider()
    render_advanced_chemometrics(processed)
    st.divider()
    render_advanced_suite(processed)
