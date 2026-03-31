"""
config.py
API キーおよび設定管理（Streamlit secrets 優先）
"""

import os
import streamlit as st
from dotenv import load_dotenv


def get_api_key() -> str | None:
    """
    Anthropic API キーを取得
    優先順位：
      1. st.secrets["ANTHROPIC_API_KEY"]（Streamlit secrets）
      2. os.getenv("ANTHROPIC_API_KEY")（.env ファイル）
      3. None（未設定）

    Returns
    -------
    str | None  API キー（なければ None）
    """
    try:
        # ① Streamlit secrets から取得（本番推奨）
        return st.secrets.get("ANTHROPIC_API_KEY")
    except FileNotFoundError:
        # st.secrets 未設定の環境では例外が発生
        pass

    try:
        # ② .env ファイルから取得（開発環境）
        load_dotenv()
        key = os.getenv("ANTHROPIC_API_KEY")
        return key if key else None
    except Exception:
        return None


def validate_api_key() -> bool:
    """API キーが設定されているか確認（Streamlit UI 用）"""
    key = get_api_key()
    return key is not None and len(key) > 0
