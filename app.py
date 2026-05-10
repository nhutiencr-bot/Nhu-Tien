import streamlit as st
import pandas as pd
from vnstock import *
from datetime import datetime, timedelta
import pytz
import plotly.express as px
import plotly.graph_objects as go
import concurrent.futures
import requests
from bs4 import BeautifulSoup
import re

# ==========================================
# 1. CÀI ĐẶT GIAO DIỆN & TIÊM CSS
# ==========================================
st.set_page_config(page_title="Fairy Invest", page_icon="🧚‍♀️", layout="wide")

st.markdown("""
<style>
    /* CSS chung */
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 18px;
        font-weight: 600;
    }
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
    }
    
    /* CSS cho Tab 5 (Kịch bản thị trường) */
    .scenario-card {
        background-color: #1e1e2f;
        color: #ffffff;
        padding: 25px;
        border-radius: 15px;
        border-left: 5px solid #ffaa00;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        margin-bottom: 20px;
    }
    .scenario-title {
        color: #ffaa00;
        font-size: 22px;
        font-weight: bold;
        margin-bottom: 15px;
    }
    .scenario-item {
        margin-bottom: 15px;
        line-height: 1.6;
    }
    .prob-badge {
        background-color: #33334d;
        padding: 3px 8px;
        border-radius: 5px;
        font-weight: bold;
        color: #ffaa00;
    }
    .right-menu-btn {
        background-color: #2a2a3c;
        color: white;
        padding: 10px 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        text-align: left;
        border: 1px solid #3f3f5a;
        cursor: pointer;
        transition: 0.3s;
    }
    .right-menu-btn:hover {
        background-color: #3f3f5a;
        border-color: #ffaa00;
    }
    .right-menu-active {
        background-color: #ffaa00;
        color: #1e1e2f;
        font-weight: bold;
        border: none;
    }
</style>
""", unsafe_allow_html=True)

#
