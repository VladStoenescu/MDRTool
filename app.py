from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Migration Dry Run Readiness Dashboard",
    page_icon="🟢",
    layout="wide",
)

DRY_RUN_DATE = date(2026, 7, 21)
DATA_DIR = Path(__file__).parent / "data"
STATUS_COLORS = {
    "Green": "#2E7D32",
    "Amber": "#F9A825",
    "Red": "#C62828",
    "Completed": "#2E7D32",
    "In Progress": "#1E88E5",
    "Not Started": "#B0BEC5",
    "Blocked": "#C62828",
    "At Risk": "#F9A825",
    "Milestone": "#6A1B9A",
}
READINESS_COLUMNS = [
    "Workstream",
    "Lead",
    "Status",
    "Progress %",
    "Key update",
    "Main risk / blocker",
    "Dependency",
    "Decision needed",
    "Next action",
    "Action owner",
    "Due date",
]
TIMELINE_COLUMNS = [
    "Activity",
    "Workstream",
    "Start Date",
    "End Date",
    "Status",
    "Owner",
]
ACTION_COLUMNS = [
    "Action ID",
    "Workstream",
    "Action description",
    "Owner",
    "Due date",
    "Status",
    "Priority",
    "Comment",
]
COMPLETED_ACTION_STATUSES = {"Done", "Completed"}


@st.cache_data
def load_sample_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    readiness_df = pd.read_csv(DATA_DIR / "readiness.csv", parse_dates=["Due date"])
    timeline_df = pd.read_csv(
        DATA_DIR / "timeline.csv", parse_dates=["Start Date", "End Date"]
    )
    actions_df = pd.read_csv(DATA_DIR / "actions.csv", parse_dates=["Due date"])
    return readiness_df, timeline_df, actions_df


def normalize_readiness_df(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized = normalized[READINESS_COLUMNS]
    normalized["Status"] = normalized["Status"].astype(str).str.title()
    normalized["Progress %"] = (
        pd.to_numeric(normalized["Progress %"], errors="coerce").fillna(0).clip(0, 100)
    )
    normalized["Due date"] = pd.to_datetime(normalized["Due date"], errors="coerce")
    return normalized


def normalize_timeline_df(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized = normalized[TIMELINE_COLUMNS]
    normalized["Start Date"] = pd.to_datetime(
        normalized["Start Date"], errors="coerce"
    )
    normalized["End Date"] = pd.to_datetime(normalized["End Date"], errors="coerce")
    normalized["Status"] = normalized["Status"].astype(str).str.title()
    return normalized


def normalize_actions_df(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized = normalized[ACTION_COLUMNS]
    normalized["Due date"] = pd.to_datetime(normalized["Due date"], errors="coerce")
    normalized["Status"] = normalized["Status"].astype(str).str.title()
    normalized["Priority"] = normalized["Priority"].astype(str).str.title()
    return normalized


def initialize_state() -> None:
    if "readiness_df" not in st.session_state:
        readiness_df, timeline_df, actions_df = load_sample_data()
        st.session_state.readiness_df = normalize_readiness_df(readiness_df)
        st.session_state.timeline_df = normalize_timeline_df(timeline_df)
        st.session_state.actions_df = normalize_actions_df(actions_df)


def handle_csv_upload(
    label: str,
    state_key: str,
    expected_columns: list[str],
    date_columns: list[str],
) -> None:
    uploaded_file = st.file_uploader(label, type="csv", key=f"upload_{state_key}")
    if not uploaded_file:
        return

    uploaded_df = pd.read_csv(uploaded_file, parse_dates=date_columns)
    missing_columns = [column for column in expected_columns if column not in uploaded_df]
    if missing_columns:
        st.error(
            f"{label} is missing required columns: {', '.join(missing_columns)}",
            icon="⚠️",
        )
        return

    st.session_state[state_key] = uploaded_df[expected_columns]
    st.success(f"{label} loaded successfully.", icon="✅")


def compute_overall_status(readiness_df: pd.DataFrame) -> str:
    statuses = readiness_df["Status"].astype(str).str.title()
    if statuses.eq("Red").any():
        return "Red"
    if statuses.eq("Amber").any():
        return "Amber"
    return "Green"


def action_is_complete(status: str) -> bool:
    return str(status).title() in COMPLETED_ACTION_STATUSES


def is_overdue(due_value: pd.Timestamp | datetime | date | str | None, status: str) -> bool:
    due_date = pd.to_datetime(due_value, errors="coerce")
    if pd.isna(due_date):
        return False
    return due_date.date() < date.today() and not action_is_complete(status)


def build_management_summary(
    readiness_df: pd.DataFrame, actions_df: pd.DataFrame, overall_status: str
) -> str:
    amber_red = readiness_df[
        readiness_df["Status"].astype(str).str.title().isin(["Amber", "Red"])
    ]["Workstream"].tolist()
    open_high = actions_df[
        actions_df["Priority"].eq("High")
        & ~actions_df["Status"].apply(action_is_complete)
    ].copy()
    open_high["Overdue"] = open_high.apply(
        lambda row: is_overdue(row["Due date"], row["Status"]), axis=1
    )
    blocked_actions = actions_df[actions_df["Status"].eq("Blocked")][
        "Action description"
    ].tolist()
    readiness_blockers = readiness_df[
        readiness_df["Status"].isin(["Amber", "Red"])
    ]["Main risk / blocker"].tolist()
    key_blockers = [
        item for item in readiness_blockers + blocked_actions if str(item).strip()
    ]
    unique_blockers = list(dict.fromkeys(key_blockers))
    blocker_text = (
        "; ".join(unique_blockers[:2])
        if unique_blockers
        else "no material blockers are currently flagged"
    )
    escalation_needed = (
        overall_status == "Red"
        or not open_high[open_high["Overdue"]].empty
        or actions_df["Status"].eq("Blocked").any()
    )
    area_text = ", ".join(amber_red) if amber_red else "no areas"
    attention_text = (
        f"{area_text} require management attention."
        if len(amber_red) != 1
        else f"{area_text} requires management attention."
    )
    escalation_text = "Escalation is recommended." if escalation_needed else "No escalation is currently required."
    return (
        f"Migration Dry Run readiness is currently {overall_status.upper()}. "
        f"{attention_text[0].upper()}{attention_text[1:]} "
        f"There are {len(open_high)} open high-priority actions, of which "
        f"{int(open_high['Overdue'].sum())} are overdue. "
        f"Key blockers: {blocker_text}. "
        f"The {DRY_RUN_DATE.strftime('%d %B %Y')} dry run remains achievable if the identified issues are closed by the next checkpoint. "
        f"{escalation_text}"
    )


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    export_df = df.copy()
    for column in export_df.columns:
        if pd.api.types.is_datetime64_any_dtype(export_df[column]):
            export_df[column] = export_df[column].dt.strftime("%Y-%m-%d")
    return export_df.to_csv(index=False).encode("utf-8")


def workbook_bytes(
    readiness_df: pd.DataFrame, timeline_df: pd.DataFrame, actions_df: pd.DataFrame
) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in {
            "Readiness": readiness_df,
            "Timeline": timeline_df,
            "Actions": actions_df,
        }.items():
            export_df = df.copy()
            for column in export_df.columns:
                if pd.api.types.is_datetime64_any_dtype(export_df[column]):
                    export_df[column] = export_df[column].dt.strftime("%Y-%m-%d")
            export_df.to_excel(writer, sheet_name=name, index=False)
    output.seek(0)
    return output.getvalue()


def readiness_card(workstream_row: pd.Series, open_actions: int, blockers: int) -> None:
    status = workstream_row["Status"]
    color = STATUS_COLORS.get(status, "#607D8B")
    st.markdown(
        f"""
        <div style="border:1px solid #dce3ea;border-left:8px solid {color};border-radius:12px;
        padding:16px;background:#ffffff;box-shadow:0 1px 4px rgba(15,23,42,0.06);height:100%;">
            <div style="font-size:1.05rem;font-weight:700;color:#0f172a;">{workstream_row["Workstream"]}</div>
            <div style="margin:8px 0 12px 0;">
                <span style="display:inline-block;background:{color};color:white;padding:4px 10px;border-radius:999px;font-size:0.85rem;">
                    {status}
                </span>
            </div>
            <div><strong>Progress:</strong> {int(workstream_row["Progress %"])}%</div>
            <div><strong>Lead:</strong> {workstream_row["Lead"]}</div>
            <div><strong>Open actions:</strong> {open_actions}</div>
            <div><strong>Blockers:</strong> {blockers}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


initialize_state()
st.title("Migration Dry Run Readiness Dashboard")

with st.expander("Data refresh options", expanded=False):
    col1, col2, col3, col4 = st.columns([1, 1, 1, 0.8])
    with col1:
        handle_csv_upload(
            "Upload readiness CSV",
            "readiness_df",
            READINESS_COLUMNS,
            ["Due date"],
        )
    with col2:
        handle_csv_upload(
            "Upload timeline CSV",
            "timeline_df",
            TIMELINE_COLUMNS,
            ["Start Date", "End Date"],
        )
    with col3:
        handle_csv_upload(
            "Upload action log CSV",
            "actions_df",
            ACTION_COLUMNS,
            ["Due date"],
        )
    with col4:
        if st.button("Reset sample data", use_container_width=True):
            readiness_df, timeline_df, actions_df = load_sample_data()
            st.session_state.readiness_df = normalize_readiness_df(readiness_df)
            st.session_state.timeline_df = normalize_timeline_df(timeline_df)
            st.session_state.actions_df = normalize_actions_df(actions_df)
            st.success("Sample data reloaded.", icon="✅")

readiness_df = normalize_readiness_df(st.session_state.readiness_df)
timeline_df = normalize_timeline_df(st.session_state.timeline_df)
actions_df = normalize_actions_df(st.session_state.actions_df)
st.session_state.readiness_df = readiness_df
st.session_state.timeline_df = timeline_df
st.session_state.actions_df = actions_df

overall_status = compute_overall_status(readiness_df)
days_remaining = (DRY_RUN_DATE - date.today()).days
last_updated = datetime.now().strftime("%d %b %Y %H:%M")

header_cols = st.columns(5)
header_cols[0].metric("Dry Run Date", DRY_RUN_DATE.strftime("%d %B %Y"))
header_cols[1].metric("Overall Readiness", overall_status)
header_cols[2].metric("Days Remaining", days_remaining)
header_cols[3].metric("Last Updated", last_updated)
header_cols[4].metric(
    "Open High Priority Actions",
    int(actions_df["Priority"].eq("High").mul(~actions_df["Status"].apply(action_is_complete)).sum()),
)

st.subheader("Overall Readiness Summary")

card_columns = st.columns(3)
for index, (_, row) in enumerate(readiness_df.iterrows()):
    workstream_actions = actions_df[actions_df["Workstream"] == row["Workstream"]]
    open_actions = int((~workstream_actions["Status"].apply(action_is_complete)).sum())
    blockers = int(workstream_actions["Status"].eq("Blocked").sum())
    with card_columns[index % 3]:
        readiness_card(row, open_actions, blockers)

st.subheader("Timeline to Dry Run")
timeline_chart_df = timeline_df.copy().sort_values(["Start Date", "End Date"])
timeline_chart_df["Display End"] = timeline_chart_df["End Date"].where(
    timeline_chart_df["End Date"] > timeline_chart_df["Start Date"],
    timeline_chart_df["End Date"] + pd.Timedelta(days=1),
)
fig = px.timeline(
    timeline_chart_df,
    x_start="Start Date",
    x_end="Display End",
    y="Activity",
    color="Status",
    text="Workstream",
    hover_data={
        "Workstream": True,
        "Start Date": "|%d %b %Y",
        "End Date": "|%d %b %Y",
        "Owner": True,
        "Status": True,
        "Display End": False,
    },
    color_discrete_map=STATUS_COLORS,
)
fig.update_yaxes(autorange="reversed")
fig.update_layout(
    height=500,
    legend_title_text="Status",
    margin=dict(l=10, r=10, t=10, b=10),
)
fig.add_vline(
    x=pd.Timestamp(DRY_RUN_DATE),
    line_width=2,
    line_dash="dash",
    line_color="#6A1B9A",
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Readiness Detail Table")
edited_readiness = st.data_editor(
    readiness_df,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "Status": st.column_config.SelectboxColumn(
            "Status",
            options=["Green", "Amber", "Red"],
        ),
        "Progress %": st.column_config.NumberColumn(
            "Progress %",
            min_value=0,
            max_value=100,
            step=5,
            format="%d%%",
        ),
        "Due date": st.column_config.DateColumn("Due date", format="YYYY-MM-DD"),
    },
)
st.session_state.readiness_df = normalize_readiness_df(edited_readiness)

st.subheader("Action Log")
actions_with_flags = actions_df.copy()
actions_with_flags["Overdue?"] = actions_with_flags.apply(
    lambda row: "🔴 Overdue" if is_overdue(row["Due date"], row["Status"]) else "",
    axis=1,
)
edited_actions = st.data_editor(
    actions_with_flags,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "Status": st.column_config.SelectboxColumn(
            "Status",
            options=["Open", "In Progress", "Done", "Blocked"],
        ),
        "Priority": st.column_config.SelectboxColumn(
            "Priority",
            options=["High", "Medium", "Low"],
        ),
        "Due date": st.column_config.DateColumn("Due date", format="YYYY-MM-DD"),
    },
    disabled=["Overdue?"],
)
st.session_state.actions_df = normalize_actions_df(
    edited_actions.drop(columns=["Overdue?"], errors="ignore")
)

overdue_actions = st.session_state.actions_df[
    st.session_state.actions_df.apply(
        lambda row: is_overdue(row["Due date"], row["Status"]), axis=1
    )
].copy()
if not overdue_actions.empty:
    st.warning(f"{len(overdue_actions)} action(s) are overdue.", icon="⚠️")
    styled_overdue = overdue_actions.style.apply(
        lambda _: ["background-color: #FDECEC"] * len(overdue_actions.columns), axis=1
    )
    st.dataframe(styled_overdue, use_container_width=True)

st.subheader("Management Summary")
summary = build_management_summary(
    st.session_state.readiness_df,
    st.session_state.actions_df,
    compute_overall_status(st.session_state.readiness_df),
)
st.info(summary)

st.subheader("Export Data")
export_cols = st.columns(4)
export_cols[0].download_button(
    "Download readiness CSV",
    data=dataframe_to_csv_bytes(st.session_state.readiness_df),
    file_name="readiness.csv",
    mime="text/csv",
    use_container_width=True,
)
export_cols[1].download_button(
    "Download timeline CSV",
    data=dataframe_to_csv_bytes(st.session_state.timeline_df),
    file_name="timeline.csv",
    mime="text/csv",
    use_container_width=True,
)
export_cols[2].download_button(
    "Download actions CSV",
    data=dataframe_to_csv_bytes(st.session_state.actions_df),
    file_name="actions.csv",
    mime="text/csv",
    use_container_width=True,
)
export_cols[3].download_button(
    "Download Excel workbook",
    data=workbook_bytes(
        st.session_state.readiness_df,
        st.session_state.timeline_df,
        st.session_state.actions_df,
    ),
    file_name="migration_dry_run_readiness.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)
