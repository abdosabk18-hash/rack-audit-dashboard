import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
from PIL import Image


# ===== PAGE CONFIG =====
st.set_page_config(
    page_title="Rack Safety Audit Dashboard",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== CUSTOM CSS =====
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460);
        padding: 20px 30px;
        border-radius: 12px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .main-header h1 {
        color: white;
        font-size: 24px;
        font-weight: 700;
        margin: 0;
    }
    .main-header p {
        color: #a0aec0;
        font-size: 13px;
        margin: 4px 0 0 0;
    }
    .kpi-card {
        background: white;
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        text-align: center;
        border-left: 4px solid #e0e0e0;
    }
    .kpi-green { border-left-color: #27ae60 !important; }
    .kpi-yellow { border-left-color: #f39c12 !important; }
    .kpi-red { border-left-color: #e74c3c !important; }
    .kpi-blue { border-left-color: #3498db !important; }
    .finding-card {
        background: #fff5f5;
        border: 1px solid #fed7d7;
        border-radius: 8px;
        padding: 12px;
        margin: 6px 0;
    }
    .ca-card {
        background: #f0fff4;
        border: 1px solid #c6f6d5;
        border-radius: 8px;
        padding: 12px;
        margin: 6px 0;
    }
    .shift-badge-morning {
        background: #fef3c7;
        color: #92400e;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }
    .shift-badge-night {
        background: #e0e7ff;
        color: #3730a3;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }
    .compliance-high { color: #27ae60; font-weight: 700; }
    .compliance-mid { color: #f39c12; font-weight: 700; }
    .compliance-low { color: #e74c3c; font-weight: 700; }
    .stDataFrame { border-radius: 8px; }
    div[data-testid="metric-container"] {
        background: white;
        border-radius: 10px;
        padding: 12px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.07);
    }
</style>
""", unsafe_allow_html=True)

# ===== SESSION STATE =====
# Supabase connection
import requests
import base64

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]
GITHUB_USER = st.secrets["GITHUB_USER"]


if 'audits' not in st.session_state:
    st.session_state.audits = []
if 'last_touch' not in st.session_state:
    st.session_state.last_touch = {}
if 'history' not in st.session_state:
    st.session_state.history = []

# ===== CONSTANTS =====
AISLES = [
    'R-1-G201','R-1-G202','R-1-G203','R-1-G204','R-1-G205',
    'R-1-G206','R-1-G207','R-1-G208','R-1-G209','R-1-G210',
    'R-1-G211','R-1-G212','R-1-G213','R-1-G214','R-1-G215',
    'R-1-G216','R-1-G217','R-1-G218','R-1-G219','R-1-G220',
    'R-1-G221','R-1-G222','R-1-G223','R-1-G224','R-1-G225',
    'R-1-G226','R-1-G227','R-1-G228','R-1-G229','R-1-G230'
]

QUESTIONS = [
    {"id": 1, "category": "Pallet Shrink Wrap",
     "text": "Are all pallets properly shrink-wrapped to secure the load?"},
    {"id": 2, "category": "Pallet Shrink Wrap",
     "text": "Is the shrink wrap intact and free from tears or loose ends?"},
    {"id": 3, "category": "Pallet Shrink Wrap",
     "text": "Are there any signs of inadequate shrink wrapping, such as loose or unstable loads?"},
    {"id": 4, "category": "Damaged Pallets",
     "text": "Are there any visibly damaged or broken pallets present in the racks area?"},
    {"id": 5, "category": "Damaged Pallets",
     "text": "Are there any sharp edges or protruding nails on pallets that could cause injuries?"},
    {"id": 6, "category": "Damaged Pallets",
     "text": "Are damaged pallets promptly removed and replaced with new ones?"},
    {"id": 7, "category": "Protruding Pallets",
     "text": "Are the pallets stored in reserve locations positioned properly within the racks?"},
    {"id": 8, "category": "Protruding Pallets",
     "text": "Are there any pallets protruding beyond the designated storage space?"},
    {"id": 9, "category": "Protruding Pallets",
     "text": "Are there any potential obstructions or hazards caused by pallets extending into walkways?"},
    {"id": 10, "category": "General Rack Safety",
     "text": "Are the racks themselves in safe condition, without visible damage or structural issues?"},
    {"id": 11, "category": "General Rack Safety",
     "text": "Do the pallets meet height compliance (max 110cm for G levels, 160cm for Non-G levels)?"},
    {"id": 12, "category": "General Rack Safety",
     "text": "Are there any signs of overloading or excessive weight on the racks?"},
    {"id": 13, "category": "Housekeeping",
     "text": "Is the racks area clean and free from debris or obstructions?"},
    {"id": 14, "category": "Housekeeping",
     "text": "Are there any spills or slippery surfaces that could pose a safety risk?"},
    {"id": 15, "category": "Housekeeping",
     "text": "Are emergency exits and evacuation routes in the racks area clear and accessible?"},
]

# ===== CORRECTIVE ACTIONS MAP =====
CA_MAP = {
    1: "Immediately shrink-wrap all unsecured pallets in the identified location. Assign associate to complete within current shift.",
    2: "Replace damaged/torn shrink wrap on affected pallets. Inspect adjacent locations for similar issues.",
    3: "Re-wrap all inadequately wrapped pallets. Conduct spot-check training for associates on proper wrapping technique.",
    4: "Remove damaged pallets immediately from rack location. Tag and quarantine for disposal or repair.",
    5: "Remove pallets with sharp edges/protruding nails immediately. File safety incident report if injury risk is high.",
    6: "Escalate to floor manager — damaged pallets not being replaced promptly. Implement immediate removal protocol.",
    7: "Reposition pallets to ensure they are fully within designated rack space. Verify with tape measure if needed.",
    8: "Push back or reposition protruding pallets immediately. Mark location for re-audit within 24 hours.",
    9: "Clear all obstructions from walkways immediately. Escalate to safety team if hazard is significant.",
    10: "Tag damaged rack for maintenance review. Do not store product on damaged rack until cleared by engineering.",
    11: "Remove non-compliant pallets exceeding height limits. Retrain associates on height compliance standards.",
    12: "Redistribute or remove excess weight from overloaded rack. Check rack load capacity label.",
    13: "Assign housekeeping to clean the area immediately. Schedule recurring cleaning check every 2 hours.",
    14: "Place wet floor signs immediately. Clean spill and identify source to prevent recurrence.",
    15: "Clear emergency exit immediately. Escalate to safety manager — this is a critical safety violation.",
}

# ===== COMPLIANCE COLOR =====
def compliance_color(pct):
    if pct >= 90:
        return "🟢", "compliance-high"
    elif pct >= 75:
        return "🟡", "compliance-mid"
    else:
        return "🔴", "compliance-low"

# ===== SAVE & LOAD =====
def save_data():
    try:
        data = {
            'audits': st.session_state.audits,
            'last_touch': st.session_state.last_touch,
            'history': st.session_state.history,
            'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        content = base64.b64encode(
            json.dumps(data, indent=2).encode()
        ).decode()
        
        url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/rack_audit_data.json"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        r = requests.get(url, headers=headers)
        sha = r.json().get('sha', '') if r.status_code == 200 else ''
        
        payload = {
            "message": "Update audit data",
            "content": content
        }
        if sha:
            payload["sha"] = sha
            
        requests.put(url, headers=headers, json=payload)
        return True
    except Exception as e:
        st.error(f"Save error: {e}")
        return False

def load_data():
    try:
        url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/rack_audit_data.json"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode()
            data = json.loads(content)
            st.session_state.audits = data.get('audits', [])
            st.session_state.last_touch = data.get('last_touch', {})
            st.session_state.history = data.get('history', [])
            return True
        return False
    except Exception as e:
        st.error(f"Load error: {e}")
        return False

def add_history(action, details):
    st.session_state.history.append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'action': action,
        'details': details
    })


# ===== PARSE CSV =====
def parse_audit_csv(uploaded_file, aisle1, aisle2, shift, audit_date):
    """Parse uploaded CSV and return structured audit records"""
    try:
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(('xlsx','xls')) else pd.read_csv(uploaded_file)
        records = []
        for _, row in df.iterrows():
            q_num = None
            answer = None
            location = None
            for col in df.columns:
                col_lower = col.lower()
                if 'yes' in col_lower or 'no' in col_lower or 'compliance' in col_lower:
                    answer = str(row[col]).strip()
                if 'location' in col_lower or 'finding' in col_lower:
                    location = str(row[col]).strip() if pd.notna(row[col]) else ''
            records.append({
                'date': str(audit_date),
                'shift': shift,
                'aisle': aisle1,
                'question_id': int(row.get('Q#', row.get('Question', 0))),
                'answer': answer,
                'finding_location': location,
                'ca': CA_MAP.get(int(row.get('Q#', 0)), '')
            })
        return records
    except Exception as e:
        st.error(f"Error parsing file: {e}")
        return []

# ===== SIDEBAR =====
with st.sidebar:
    try:
        logo = Image.open("Banner1.png")
        st.image(logo, width=250)
    except:
        st.markdown("### 🏭 Operations & Safety")


    st.markdown("---")
    st.markdown("**Rack Safety Audit Dashboard**")
    st.markdown("*EG Fulfillment Center*")
    st.markdown("---")

    page = st.radio("📍 Navigation", [
        "📥 Upload Audit",
        "📋 Manual Entry",
        "📊 Overview Dashboard",
        "📈 Weekly Trend",
        "⚠️ Findings & CA",
        "👤 Last Touch Tracker",
        "📜 Audit History",
        "⚙️ Settings"
    ])

    st.markdown("---")
    if st.button("📂 Load Saved Data"):
        if load_data():
            st.success("✅ Data loaded!")
            st.rerun()
        else:
            st.warning("No saved data found.")

    total_audits = len(st.session_state.audits)
    st.metric("Total Audits Logged", total_audits)
# ===== HEADER =====
st.markdown("""
<div class="main-header">
    <div>
        <h1>🏭 Rack Safety Audit Dashboard</h1>
        <p>EG Fulfillment Center | Operations & Safety | Daily Rack Audit Tracker</p>
    </div>
    <div style="text-align:right;color:#a0aec0;font-size:13px;">
        """ + datetime.now().strftime('%A, %d %B %Y') + """
    </div>
</div>
""", unsafe_allow_html=True)

# ===================================================
# PAGE: UPLOAD AUDIT
# ===================================================
if page == "📥 Upload Audit":
    st.title("📥 Upload Daily Audit File")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        audit_date = st.date_input("📅 Audit Date", value=datetime.now())
    with col2:
        shift = st.selectbox("🌅 Shift", ["Morning", "Night"])
    with col3:
        aisle1 = st.selectbox("🏷️ Aisle 1", AISLES)
    with col4:
        aisle2 = st.selectbox("🏷️ Aisle 2", [a for a in AISLES if a != aisle1])

    st.markdown("---")
    uploaded_file = st.file_uploader(
        "📎 Upload Audit File (Excel or CSV)",
        type=['xlsx', 'xls', 'csv']
    )

    if uploaded_file:
        try:
            if uploaded_file.name.endswith(('xlsx', 'xls')):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(uploaded_file)

            st.success(f"✅ File loaded: {len(df)} rows")
            st.dataframe(df.head(5), use_container_width=True)

            if st.button("✅ Process & Save Audit", use_container_width=True):
                new_records = []

                # Aisle 1
                for _, row in df.iterrows():
                    try:
                        q_id = int(row['Q#'])
                    except:
                        continue
                    answer1 = str(row.get('Yes/No Aisle1', 'Yes')).strip()
                    is_finding1 = answer1.lower() in ['no', 'n', 'false', '0']
                    loc1 = str(row.get('Finding Location Aisle1', '')).strip()
                    if loc1 == 'nan': loc1 = ''
                    record1 = {
                        'date': str(audit_date),
                        'shift': shift,
                        'aisle': aisle1,
                        'question_id': q_id,
                        'question_text': next((q['text'] for q in QUESTIONS if q['id'] == q_id), f'Question {q_id}'),
                        'category': next((q['category'] for q in QUESTIONS if q['id'] == q_id), 'General'),
                        'answer': 'No' if is_finding1 else 'Yes',
                        'is_finding': is_finding1,
                        'finding_location': loc1,
                        'ca': CA_MAP.get(q_id, '') if is_finding1 else '',
                        'ca_status': 'Open' if is_finding1 else '',
                        'logged_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    new_records.append(record1)

                # Aisle 2
                for _, row in df.iterrows():
                    try:
                        q_id = int(row['Q#'])
                    except:
                        continue
                    answer2 = str(row.get('Yes/No Aisle2', 'Yes')).strip()
                    is_finding2 = answer2.lower() in ['no', 'n', 'false', '0']
                    loc2 = str(row.get('Finding Location Aisle2', '')).strip()
                    if loc2 == 'nan': loc2 = ''
                    record2 = {
                        'date': str(audit_date),
                        'shift': shift,
                        'aisle': aisle2,
                        'question_id': q_id,
                        'question_text': next((q['text'] for q in QUESTIONS if q['id'] == q_id), f'Question {q_id}'),
                        'category': next((q['category'] for q in QUESTIONS if q['id'] == q_id), 'General'),
                        'answer': 'No' if is_finding2 else 'Yes',
                        'is_finding': is_finding2,
                        'finding_location': loc2,
                        'ca': CA_MAP.get(q_id, '') if is_finding2 else '',
                        'ca_status': 'Open' if is_finding2 else '',
                        'logged_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    new_records.append(record2)

                st.session_state.audits.extend(new_records)
                add_history('Audit Uploaded',
                    f'{shift} | {aisle1} & {aisle2} | {audit_date} | {len(new_records)} records')
                save_data()
                st.success(f"✅ Saved {len(new_records)} audit records!")
                st.balloons()
                st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")

# ===================================================
# PAGE: MANUAL ENTRY
# ===================================================
elif page == "📋 Manual Entry":
    st.title("📋 Manual Audit Entry")
    st.info("Enter audit results manually — question by question")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        audit_date = st.date_input("📅 Audit Date", value=datetime.now())
    with col2:
        shift = st.selectbox("🌅 Shift", ["Morning", "Night"])
    with col3:
        aisle1 = st.selectbox("🏷️ Aisle 1", AISLES)
    with col4:
        aisle2 = st.selectbox("🏷️ Aisle 2", [a for a in AISLES if a != aisle1])

    st.markdown("---")

    for aisle in [aisle1, aisle2]:
        st.markdown(f"### 🏷️ Aisle: **{aisle}**")
        shift_badge = "shift-badge-morning" if shift == "Morning" else "shift-badge-night"
        st.markdown(f'<span class="{shift_badge}">{"🌅 Morning Shift" if shift == "Morning" else "🌙 Night Shift"}</span>', unsafe_allow_html=True)
        st.markdown("")

        current_category = ""
        aisle_answers = {}
        aisle_locations = {}

        for q in QUESTIONS:
            if q['category'] != current_category:
                current_category = q['category']
                st.markdown(f"**📂 {current_category}**")

            col_q, col_a, col_l = st.columns([4, 1, 2])
            with col_q:
                st.markdown(f"<small>**Q{q['id']}:** {q['text']}</small>", unsafe_allow_html=True)
            with col_a:
                answer = st.selectbox(
                    "Answer",
                    ["Yes", "No"],
                    key=f"ans_{aisle}_{q['id']}",
                    label_visibility="collapsed"
                )
                aisle_answers[q['id']] = answer
            with col_l:
                if answer == "No":
                    loc = st.text_input(
                        "Finding Location",
                        placeholder="e.g. C61",
                        key=f"loc_{aisle}_{q['id']}",
                        label_visibility="collapsed"
                    )
                    aisle_locations[q['id']] = loc
                else:
                    aisle_locations[q['id']] = ''

        findings_count = sum(1 for v in aisle_answers.values() if v == "No")
        total_q = len(QUESTIONS)
        compliance = round(((total_q - findings_count) / total_q) * 100, 1)
        emoji, css = compliance_color(compliance)
        st.markdown(f"**{aisle} Preview:** {emoji} Compliance: **{compliance}%** | Findings: **{findings_count}**")
        st.markdown("---")

    if st.button("💾 Save All Audit Entries", use_container_width=True, type="primary"):
        new_records = []
        for aisle in [aisle1, aisle2]:
            for q in QUESTIONS:
                key_a = f"ans_{aisle}_{q['id']}"
                key_l = f"loc_{aisle}_{q['id']}"
                answer = st.session_state.get(key_a, 'Yes')
                loc = st.session_state.get(key_l, '')
                is_finding = answer == 'No'
                record = {
                    'date': str(audit_date),
                    'shift': shift,
                    'aisle': aisle,
                    'question_id': q['id'],
                    'question_text': q['text'],
                    'category': q['category'],
                    'answer': answer,
                    'is_finding': is_finding,
                    'finding_location': loc,
                    'ca': CA_MAP.get(q['id'], '') if is_finding else '',
                    'ca_status': 'Open' if is_finding else '',
                    'logged_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                new_records.append(record)

        st.session_state.audits.extend(new_records)
        add_history('Manual Entry', f'{shift} | {aisle1} & {aisle2} | {audit_date}')
        save_data()
        st.success(f"✅ Saved {len(new_records)} records!")
        st.balloons()

# ===================================================
# PAGE: OVERVIEW DASHBOARD
# ===================================================
elif page == "📊 Overview Dashboard":
    st.title("📊 Overview Dashboard")

    if not st.session_state.audits:
        st.warning("⚠️ No audit data yet. Please upload or enter audit data first.")
    else:
        df = pd.DataFrame(st.session_state.audits)
        df['date'] = pd.to_datetime(df['date'])

        # ── Filters ──
        col1, col2, col3 = st.columns(3)
        with col1:
            date_range = st.date_input("📅 Date Range",
                value=(df['date'].min().date(), df['date'].max().date()))
        with col2:
            shift_filter = st.multiselect("🌅 Shift",
                options=['Morning', 'Night'], default=['Morning', 'Night'])
        with col3:
            aisle_filter = st.multiselect("🏷️ Aisles",
                options=sorted(df['aisle'].unique().tolist()),
                default=sorted(df['aisle'].unique().tolist()))

        # Apply filters
        mask = (
            (df['date'].dt.date >= date_range[0]) &
            (df['date'].dt.date <= date_range[1]) &
            (df['shift'].isin(shift_filter)) &
            (df['aisle'].isin(aisle_filter))
        )
        fdf = df[mask].copy()

        if fdf.empty:
            st.warning("No data for selected filters.")
        else:
            # ── KPI Cards ──
            st.markdown("### 🎯 Key Metrics")
            total_q = len(fdf)
            total_findings = fdf['is_finding'].sum()
            compliance_overall = round(((total_q - total_findings) / total_q) * 100, 1) if total_q > 0 else 0
            open_ca = len(fdf[(fdf['is_finding'] == True) & (fdf['ca_status'] == 'Open')])
            audits_done = fdf.groupby(['date', 'shift', 'aisle']).ngroups

            emoji, _ = compliance_color(compliance_overall)

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("📋 Audits Completed", audits_done)
            col2.metric("✅ Overall Compliance", f"{compliance_overall}% {emoji}")
            col3.metric("⚠️ Total Findings", int(total_findings))
            col4.metric("🔴 Open CAs", open_ca)
            col5.metric("📊 Questions Checked", total_q)

            st.markdown("---")

            # ── Compliance by Aisle ──
            st.markdown("### 🏷️ Compliance by Aisle")
            aisle_stats = fdf.groupby('aisle').agg(
                total=('question_id', 'count'),
                findings=('is_finding', 'sum')
            ).reset_index()
            aisle_stats['compliance'] = round(
                ((aisle_stats['total'] - aisle_stats['findings']) / aisle_stats['total']) * 100, 1)
            aisle_stats['color'] = aisle_stats['compliance'].apply(
                lambda x: '#27ae60' if x >= 90 else ('#f39c12' if x >= 75 else '#e74c3c'))
            aisle_stats = aisle_stats.sort_values('compliance', ascending=True)

            fig_aisle = go.Figure()
            fig_aisle.add_trace(go.Bar(
                x=aisle_stats['compliance'],
                y=aisle_stats['aisle'],
                orientation='h',
                marker_color=aisle_stats['color'],
                text=aisle_stats['compliance'].apply(lambda x: f'{x}%'),
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>Compliance: %{x}%<extra></extra>'
            ))
            fig_aisle.add_vline(x=90, line_dash="dash", line_color="#27ae60",
                               annotation_text="Target 90%", annotation_position="top")
            fig_aisle.update_layout(
                title="Compliance % by Aisle",
                xaxis_title="Compliance %",
                xaxis=dict(range=[0, 110]),
                height=max(400, len(aisle_stats) * 28),
                plot_bgcolor='white',
                paper_bgcolor='white',
                showlegend=False
            )
            st.plotly_chart(fig_aisle, use_container_width=True)

            # ── Findings by Category ──
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 📂 Findings by Category")
                cat_findings = fdf[fdf['is_finding'] == True].groupby('category').size().reset_index(name='count')
                if not cat_findings.empty:
                    fig_cat = px.pie(
                        cat_findings, values='count', names='category',
                        title="Findings Distribution by Category",
                        color_discrete_sequence=['#e74c3c','#f39c12','#3498db','#9b59b6']
                    )
                    fig_cat.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_cat, use_container_width=True)
                else:
                    st.success("✅ No findings in selected period!")

            with col2:
                st.markdown("### 🌅 Morning vs Night Compliance")
                shift_stats = fdf.groupby('shift').agg(
                    total=('question_id', 'count'),
                    findings=('is_finding', 'sum')
                ).reset_index()
                shift_stats['compliance'] = round(
                    ((shift_stats['total'] - shift_stats['findings']) / shift_stats['total']) * 100, 1)

                fig_shift = go.Figure()
                colors = {'Morning': '#f39c12', 'Night': '#3498db'}
                for _, row in shift_stats.iterrows():
                    fig_shift.add_trace(go.Bar(
                        name=row['shift'],
                        x=[row['shift']],
                        y=[row['compliance']],
                        marker_color=colors.get(row['shift'], '#666'),
                        text=f"{row['compliance']}%",
                        textposition='outside'
                    ))
                fig_shift.add_hline(y=90, line_dash="dash", line_color="#27ae60",
                                   annotation_text="Target 90%")
                fig_shift.update_layout(
                    title="Compliance by Shift",
                    yaxis=dict(range=[0, 110], title="Compliance %"),
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    showlegend=False,
                    height=350
                )
                st.plotly_chart(fig_shift, use_container_width=True)

            # ── Aisle Summary Table ──
            st.markdown("### 📋 Aisle Summary Table")
            aisle_table = aisle_stats.copy()
            aisle_table['Status'] = aisle_table['compliance'].apply(
                lambda x: '🟢 Good' if x >= 90 else ('🟡 Needs Attention' if x >= 75 else '🔴 Critical'))
            aisle_table = aisle_table.rename(columns={
                'aisle': 'Aisle', 'total': 'Questions Checked',
                'findings': 'Findings', 'compliance': 'Compliance %'
            })[['Aisle', 'Questions Checked', 'Findings', 'Compliance %', 'Status']]
            st.dataframe(aisle_table.sort_values('Compliance %'), use_container_width=True)
# ===================================================
# PAGE: WEEKLY TREND
# ===================================================
elif page == "📈 Weekly Trend":
    st.title("📈 Weekly Compliance Trend")

    if not st.session_state.audits:
        st.warning("⚠️ No audit data yet.")
    else:
        df = pd.DataFrame(st.session_state.audits)
        df['date'] = pd.to_datetime(df['date'])

        # ── Daily Compliance Trend ──
        st.markdown("### 📅 Daily Compliance Trend")
        daily = df.groupby(['date', 'aisle']).agg(
            total=('question_id', 'count'),
            findings=('is_finding', 'sum')
        ).reset_index()
        daily['compliance'] = round(
            ((daily['total'] - daily['findings']) / daily['total']) * 100, 1)

        aisle_select = st.multiselect(
            "Select Aisles to Compare",
            options=sorted(df['aisle'].unique().tolist()),
            default=sorted(df['aisle'].unique().tolist())[:5]
        )

        daily_filtered = daily[daily['aisle'].isin(aisle_select)]

        fig_trend = px.line(
            daily_filtered,
            x='date', y='compliance',
            color='aisle',
            markers=True,
            title="Daily Compliance % per Aisle",
            labels={'compliance': 'Compliance %', 'date': 'Date', 'aisle': 'Aisle'}
        )
        fig_trend.add_hline(
            y=90, line_dash="dash", line_color="#27ae60",
            annotation_text="Target 90%", annotation_position="top right"
        )
        fig_trend.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            yaxis=dict(range=[0, 110]),
            height=450,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig_trend, use_container_width=True)

        # ── Weekly Average per Aisle ──
        st.markdown("### 📊 Weekly Average Compliance per Aisle")
        df['week'] = df['date'].dt.isocalendar().week.astype(str)
        weekly = df.groupby(['week', 'aisle']).agg(
            total=('question_id', 'count'),
            findings=('is_finding', 'sum')
        ).reset_index()
        weekly['compliance'] = round(
            ((weekly['total'] - weekly['findings']) / weekly['total']) * 100, 1)

        fig_weekly = px.bar(
            weekly[weekly['aisle'].isin(aisle_select)],
            x='aisle', y='compliance',
            color='week', barmode='group',
            title="Weekly Compliance % by Aisle",
            labels={'compliance': 'Compliance %', 'aisle': 'Aisle', 'week': 'Week'},
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig_weekly.add_hline(y=90, line_dash="dash", line_color="#27ae60",
                            annotation_text="Target 90%")
        fig_weekly.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            yaxis=dict(range=[0, 110]), height=400
        )
        st.plotly_chart(fig_weekly, use_container_width=True)

        # ── Findings Trend ──
        st.markdown("### ⚠️ Daily Findings Count Trend")
        daily_findings = df.groupby('date').agg(
            findings=('is_finding', 'sum'),
            total=('question_id', 'count')
        ).reset_index()
        daily_findings['compliance'] = round(
            ((daily_findings['total'] - daily_findings['findings']) / daily_findings['total']) * 100, 1)

        fig_findings_trend = go.Figure()
        fig_findings_trend.add_trace(go.Bar(
            x=daily_findings['date'],
            y=daily_findings['findings'],
            name='Findings',
            marker_color='#e74c3c',
            opacity=0.7
        ))
        fig_findings_trend.add_trace(go.Scatter(
            x=daily_findings['date'],
            y=daily_findings['compliance'],
            name='Compliance %',
            yaxis='y2',
            line=dict(color='#27ae60', width=3),
            mode='lines+markers'
        ))
        fig_findings_trend.update_layout(
            title="Daily Findings Count vs Compliance %",
            yaxis=dict(title="Findings Count"),
            yaxis2=dict(title="Compliance %", overlaying='y', side='right', range=[0, 110]),
            plot_bgcolor='white', paper_bgcolor='white',
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig_findings_trend, use_container_width=True)

        # ── Shift Comparison Trend ──
        st.markdown("### 🌅🌙 Morning vs Night Shift Trend")
        shift_daily = df.groupby(['date', 'shift']).agg(
            total=('question_id', 'count'),
            findings=('is_finding', 'sum')
        ).reset_index()
        shift_daily['compliance'] = round(
            ((shift_daily['total'] - shift_daily['findings']) / shift_daily['total']) * 100, 1)

        fig_shift_trend = px.line(
            shift_daily, x='date', y='compliance',
            color='shift', markers=True,
            title="Morning vs Night Shift Compliance Trend",
            color_discrete_map={'Morning': '#f39c12', 'Night': '#3498db'},
            labels={'compliance': 'Compliance %', 'date': 'Date'}
        )
        fig_shift_trend.add_hline(y=90, line_dash="dash", line_color="#27ae60",
                                  annotation_text="Target 90%")
        fig_shift_trend.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            yaxis=dict(range=[0, 110]), height=380
        )
        st.plotly_chart(fig_shift_trend, use_container_width=True)

        # ── Heatmap ──
        st.markdown("### 🗺️ Compliance Heatmap — Aisle × Date")
        pivot = daily.pivot_table(
            index='aisle', columns='date', values='compliance', aggfunc='mean')
        pivot.columns = [str(c.date()) for c in pivot.columns]

        fig_heat = px.imshow(
            pivot,
            color_continuous_scale=['#e74c3c', '#f39c12', '#27ae60'],
            zmin=0, zmax=100,
            title="Compliance Heatmap (Green = Good, Red = Critical)",
            labels=dict(color="Compliance %")
        )
        fig_heat.update_layout(height=max(400, len(pivot) * 25))
        st.plotly_chart(fig_heat, use_container_width=True)


# ===================================================
# PAGE: FINDINGS & CA
# ===================================================
elif page == "⚠️ Findings & CA":
    st.title("⚠️ Findings & Corrective Actions")

    if not st.session_state.audits:
        st.warning("⚠️ No audit data yet.")
    else:
        df = pd.DataFrame(st.session_state.audits)
        df['date'] = pd.to_datetime(df['date'])
        findings_df = df[df['is_finding'] == True].copy()

        if findings_df.empty:
            st.success("✅ No findings recorded! Excellent compliance.")
        else:
            # ── Filters ──
            col1, col2, col3 = st.columns(3)
            with col1:
                ca_status_filter = st.multiselect(
                    "CA Status", ['Open', 'Closed', 'In Progress'],
                    default=['Open', 'In Progress'])
            with col2:
                aisle_f = st.multiselect(
                    "Aisle", sorted(findings_df['aisle'].unique().tolist()),
                    default=sorted(findings_df['aisle'].unique().tolist()))
            with col3:
                cat_f = st.multiselect(
                    "Category", sorted(findings_df['category'].unique().tolist()),
                    default=sorted(findings_df['category'].unique().tolist()))

            mask = (
                findings_df['ca_status'].isin(ca_status_filter) &
                findings_df['aisle'].isin(aisle_f) &
                findings_df['category'].isin(cat_f)
            )
            filt_findings = findings_df[mask].copy()

            # ── Summary ──
            col1, col2, col3 = st.columns(3)
            col1.metric("⚠️ Total Findings", len(filt_findings))
            col2.metric("🔴 Open CAs",
                len(filt_findings[filt_findings['ca_status'] == 'Open']))
            col3.metric("✅ Closed CAs",
                len(filt_findings[filt_findings['ca_status'] == 'Closed']))

            st.markdown("---")

            # ── Findings Cards ──
            st.markdown("### 📋 Findings Detail")
            for i, (idx, row) in enumerate(filt_findings.iterrows()):
                emoji_status = "🔴" if row['ca_status'] == 'Open' else (
                    "🟡" if row['ca_status'] == 'In Progress' else "🟢")

                with st.expander(
                    f"{emoji_status} **Q{row['question_id']}** | {row['aisle']} | "
                    f"{row['category']} | {str(row['date'])[:10]} | {row['shift']} Shift"
                ):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"""
                        <div class="finding-card">
                            <strong>🔍 Finding:</strong><br>
                            {row['question_text']}<br><br>
                            <strong>📍 Location:</strong> {row.get('finding_location', 'Not specified')}<br>
                            <strong>🏷️ Aisle:</strong> {row['aisle']} |
                            <strong>📅 Date:</strong> {str(row['date'])[:10]} |
                            <strong>🌅 Shift:</strong> {row['shift']}
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown(f"""
                        <div class="ca-card">
                            <strong>⚙️ Corrective Action:</strong><br>
                            {row['ca']}
                        </div>
                        """, unsafe_allow_html=True)

                    with col2:
                        st.markdown("**Update CA Status:**")
                        new_status = st.selectbox(
                            "Status",
                            ['Open', 'In Progress', 'Closed'],
                            index=['Open', 'In Progress', 'Closed'].index(
                                row.get('ca_status', 'Open')),
                            key=f"ca_status_{idx}"
                        )
                        ca_note = st.text_area(
                            "CA Notes",
                            value=row.get('ca_notes', ''),
                            key=f"ca_note_{idx}",
                            height=80
                        )
                        if st.button("💾 Update", key=f"update_ca_{idx}"):
                            st.session_state.audits[idx]['ca_status'] = new_status
                            st.session_state.audits[idx]['ca_notes'] = ca_note
                            st.session_state.audits[idx]['ca_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M')
                            add_history('CA Updated',
                                f'Q{row["question_id"]} | {row["aisle"]} → {new_status}')
                            save_data()
                            st.success("✅ Updated!")
                            st.rerun()

            # ── Export Findings ──
            st.markdown("---")
            if st.button("📥 Export Findings to Excel"):
                export_df = filt_findings[[
                    'date', 'shift', 'aisle', 'category',
                    'question_id', 'question_text',
                    'finding_location', 'ca', 'ca_status'
                ]].copy()
                export_df['date'] = export_df['date'].astype(str)
                fname = f"findings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                export_df.to_excel(fname, index=False)
                with open(fname, 'rb') as f:
                    st.download_button(
                        "⬇️ Download Findings Excel",
                        data=f, file_name=fname,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )


# ===================================================
# PAGE: LAST TOUCH TRACKER
# ===================================================
elif page == "👤 Last Touch Tracker":
    st.title("👤 Last Touch Tracker")
    st.info("Track the last person who touched each rack location")

    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("### ➕ Add / Update Last Touch")
        with st.form("last_touch_form"):
            lt_aisle = st.selectbox("Aisle", AISLES)
            lt_location = st.text_input("Location (e.g. C61, E131)", placeholder="C61")
            lt_user = st.text_input("Associate Name / ID")
            lt_date = st.date_input("Date", value=datetime.now())
            lt_shift = st.selectbox("Shift", ["Morning", "Night"])
            lt_note = st.text_input("Note (optional)", placeholder="e.g. Restocked, Moved pallet")

            if st.form_submit_button("💾 Save Last Touch", use_container_width=True):
                key = f"{lt_aisle}_{lt_location}"
                st.session_state.last_touch[key] = {
                    'aisle': lt_aisle,
                    'location': lt_location,
                    'user': lt_user,
                    'date': str(lt_date),
                    'shift': lt_shift,
                    'note': lt_note,
                    'logged_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                add_history('Last Touch Updated',
                    f'{lt_aisle} | {lt_location} | {lt_user} | {lt_date}')
                save_data()
                st.success(f"✅ Saved! {lt_aisle} - {lt_location} → {lt_user}")
                st.rerun()

    with col2:
        st.markdown("### 📋 Last Touch Records")
        if st.session_state.last_touch:
            lt_df = pd.DataFrame(st.session_state.last_touch.values())
            lt_df = lt_df.sort_values(['aisle', 'location'])

            search_lt = st.text_input("🔍 Search by Aisle or User", "")
            if search_lt:
                lt_df = lt_df[
                    lt_df['aisle'].str.contains(search_lt, case=False) |
                    lt_df['user'].str.contains(search_lt, case=False) |
                    lt_df['location'].str.contains(search_lt, case=False)
                ]

            aisle_filter_lt = st.multiselect(
                "Filter by Aisle",
                options=sorted(lt_df['aisle'].unique().tolist()),
                default=[]
            )
            if aisle_filter_lt:
                lt_df = lt_df[lt_df['aisle'].isin(aisle_filter_lt)]

            st.dataframe(
                lt_df[['aisle', 'location', 'user', 'date', 'shift', 'note']].rename(columns={
                    'aisle': 'Aisle', 'location': 'Location',
                    'user': 'Associate', 'date': 'Date',
                    'shift': 'Shift', 'note': 'Note'
                }),
                use_container_width=True
            )

            st.metric("Total Locations Tracked", len(lt_df))

            if st.button("📥 Export Last Touch"):
                fname = f"last_touch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                lt_df.to_excel(fname, index=False)
                with open(fname, 'rb') as f:
                    st.download_button(
                        "⬇️ Download Excel", data=f, file_name=fname,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        else:
            st.info("No last touch records yet. Add your first record!")


# ===================================================
# PAGE: AUDIT HISTORY
# ===================================================
elif page == "📜 Audit History":
    st.title("📜 Audit History")

    if not st.session_state.audits:
        st.warning("No audit data yet.")
    else:
        df = pd.DataFrame(st.session_state.audits)
        df['date'] = pd.to_datetime(df['date'])

        st.markdown("### 📅 Audit Sessions")
        sessions = df.groupby(['date', 'shift', 'aisle']).agg(
            total=('question_id', 'count'),
            findings=('is_finding', 'sum'),
            logged_at=('logged_at', 'first')
        ).reset_index()
        sessions['compliance'] = round(
            ((sessions['total'] - sessions['findings']) / sessions['total']) * 100, 1)
        sessions['status'] = sessions['compliance'].apply(
            lambda x: '🟢 Good' if x >= 90 else ('🟡 Attention' if x >= 75 else '🔴 Critical'))
        sessions = sessions.sort_values('date', ascending=False)

        st.dataframe(
            sessions.rename(columns={
                'date': 'Date', 'shift': 'Shift', 'aisle': 'Aisle',
                'total': 'Questions', 'findings': 'Findings',
                'compliance': 'Compliance %', 'status': 'Status',
                'logged_at': 'Logged At'
            }),
            use_container_width=True
        )

        st.markdown("---")
        st.markdown("### 🕐 Change Log")
        if st.session_state.history:
            for change in reversed(st.session_state.history[-30:]):
                with st.expander(
                    f"🕐 {change['timestamp']} — {change['action']}"
                ):
                    st.write(change['details'])
        else:
            st.info("No changes logged yet.")


# ===================================================
# PAGE: SETTINGS
# ===================================================
elif page == "⚙️ Settings":
    st.title("⚙️ Settings")

    st.markdown("### 🎯 Compliance Thresholds")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="kpi-card kpi-green">
            <div style="font-size:11px;color:#666;text-transform:uppercase">Good</div>
            <div style="font-size:28px;font-weight:700;color:#27ae60">≥ 90%</div>
            <div style="font-size:11px;color:#27ae60">🟢 Target Met</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="kpi-card kpi-yellow">
            <div style="font-size:11px;color:#666;text-transform:uppercase">Needs Attention</div>
            <div style="font-size:28px;font-weight:700;color:#f39c12">75–89%</div>
            <div style="font-size:11px;color:#f39c12">🟡 Monitor Closely</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="kpi-card kpi-red">
            <div style="font-size:11px;color:#666;text-transform:uppercase">Critical</div>
            <div style="font-size:28px;font-weight:700;color:#e74c3c">< 75%</div>
            <div style="font-size:11px;color:#e74c3c">🔴 Immediate Action</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📊 Data Management")

    col1, col2 = st.columns(2)
    with col1:
        if st.session_state.audits:
            st.success(f"✅ {len(st.session_state.audits)} audit records loaded")
            if st.button("💾 Save Data Now"):
                save_data()
                st.success("✅ Data saved!")

            if st.button("📥 Export All Data to Excel"):
                df_export = pd.DataFrame(st.session_state.audits)
                fname = f"rack_audit_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                df_export.to_excel(fname, index=False)
                with open(fname, 'rb') as f:
                    st.download_button(
                        "⬇️ Download Full Data",
                        data=f, file_name=fname,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
        else:
            st.info("No data loaded yet.")

    with col2:
        st.markdown("### ⚠️ Danger Zone")
        if st.button("🗑️ Clear All Audit Data", type="secondary"):
            confirm = st.checkbox("I confirm I want to delete all data")
            if confirm:
                st.session_state.audits = []
                st.session_state.last_touch = {}
                st.session_state.history = []
                if os.path.exists('rack_audit_data.json'):
                    os.remove('rack_audit_data.json')
                st.success("✅ All data cleared!")
                st.rerun()

    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.info("""
    **Rack Safety Audit Dashboard**
    - Version: 1.0
    - Built for: EG Fulfillment Center
    - Purpose: Daily rack safety audit tracking & compliance monitoring
    - Audits: 2 aisles per shift × 2 shifts = 4 aisles/day
    - Aisles: R-1-G201 to R-1-G230 (30 aisles total)
    """)
