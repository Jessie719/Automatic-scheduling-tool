import streamlit as st
import pandas as pd
from datetime import datetime, time, timedelta

st.title("📅 自動排班工具")

# ===== 中文星期函數 =====
def weekday_bracket(date):
    weekdays = ["一","二","三","四","五","六","日"]
    return f"({weekdays[date.weekday()]})"

# ===== 時段初始設定 =====
if "shifts" not in st.session_state:
    st.session_state.shifts = {
        "08:00-11:00": {"count": 1},
        "11:00-16:30": {"count": 2},
        "16:30-18:30": {"count": 1},
        "18:30-22:00": {"count": 2}
    }

# 固定班別用於填補空缺
if "fixed_shifts" not in st.session_state:
    st.session_state.fixed_shifts = st.session_state.shifts.copy()

def shift_hours(shift_str):
    start, end = shift_str.split("-")
    start_dt = datetime.strptime(start, "%H:%M")
    end_dt = datetime.strptime(end, "%H:%M")
    hours = (end_dt - start_dt).seconds / 3600
    return hours

# ===== 日期選擇 =====
start_date = st.date_input("開始日期", datetime.today())
st.write(f"開始日期：{start_date.strftime('%Y-%m-%d')}{weekday_bracket(start_date)}")
end_date = st.date_input("結束日期", datetime.today() + timedelta(days=6))
st.write(f"結束日期：{end_date.strftime('%Y-%m-%d')}{weekday_bracket(end_date)}")

if start_date > end_date:
    st.error("⚠️ 結束日期不能早於開始日期")
    st.stop()

date_range = pd.date_range(start=start_date, end=end_date)
dates_display = [f"{d.strftime('%Y-%m-%d')}{weekday_bracket(d)}" for d in date_range]

# ===== 人員設定 =====
default_staff = ["儒", "忻", "瑄", "峮", "米", "姿", "A"]
num_staff = st.number_input("人員數量", min_value=1, max_value=20, value=len(default_staff))
staff = []
fill_in_staff = {}
for i in range(num_staff):
    default_name = default_staff[i] if i < len(default_staff) else f"員工{i+1}"
    name = st.text_input(f"輸入人員 {i+1} 名字", value=default_name)
    staff.append(name)
    fill_in = st.checkbox("填補空缺", key=f"fillin_{name}")
    fill_in_staff[name] = fill_in

# ===== 班別管理 =====
st.subheader("🕒 班別設定")
st.write("可新增或刪除班別（固定班別除外），時間範圍 08:00~22:00。")

with st.expander("新增班別"):
    start_t = st.time_input("開始時間", value=time(8,0))
    end_t = st.time_input("結束時間", value=time(22,0))
    count = st.number_input("需求人數", min_value=1, max_value=10, value=1)
    if st.button("新增"):
        # 限制時間範圍
        if start_t < time(8,0):
            st.warning("⚠️ 開始時間不可早於 08:00")
        elif end_t > time(22,0):
            st.warning("⚠️ 結束時間不可晚於 22:00")
        elif start_t >= end_t:
            st.error("結束時間必須大於開始時間")
        else:
            key = f"{start_t.strftime('%H:%M')}-{end_t.strftime('%H:%M')}"
            if key in st.session_state.shifts:
                st.warning("⚠️ 班別已存在")
            else:
                st.session_state.shifts[key] = {"count": count}
                st.rerun()

for shift, info in list(st.session_state.shifts.items()):
    st.write(f"{shift} → 需求 {info['count']} 人（{shift_hours(shift)} 小時）")
    # 如果這個班別是固定班別，則不顯示刪除按鈕
    if shift not in st.session_state.fixed_shifts:
        if st.button(f"刪除 {shift}", key=f"del_{shift}"):
            del st.session_state.shifts[shift]
            st.rerun()

# ===== 特別需求設定 =====
st.subheader("⚙️ 特別需求設定")
st.write("勾選為填補空缺人員不設定")
availability = {}
unavailable_days = {}
max_days_per_week = {}

for person in staff:
    if fill_in_staff[person]:
        continue
    availability[person] = []
    unavailable_days[person] = []
    max_days_per_week[person] = None
    with st.expander(f"設定 {person}"):
        # 按開始時間排序 shifts
        sorted_shifts = sorted(
            st.session_state.shifts.keys(),
            key=lambda s: datetime.strptime(s.split("-")[0], "%H:%M")
        )
        allowed_shifts = st.multiselect(f"{person} 可排班時段（空白代表全部）", sorted_shifts, placeholder="請選擇可排班時段（可多選）")
        availability[person] = allowed_shifts if allowed_shifts else list(st.session_state.shifts.keys())
        days_off = st.multiselect(f"{person} 不可排班日期", options=dates_display, placeholder="請選擇不可排班日期（可多選）")
        unavailable_days[person] = days_off
        limit_input = st.text_input(f"{person} 每週最多上幾天（空白代表無限制）")
        try:
            limit = int(limit_input)
            if limit < 1:
                limit = None
        except:
            limit = None
        max_days_per_week[person] = limit

# ===== 工具函數 =====
def shift_to_tuple(shift_str):
    start, end = shift_str.split("-")
    return datetime.strptime(start, "%H:%M"), datetime.strptime(end, "%H:%M")

def get_covered_count(target_shift, assigned_shifts):
    target_start, target_end = shift_to_tuple(target_shift)
    target_duration = (target_end - target_start).total_seconds() / 3600
    coverage_by_person = {}

    for s, person in assigned_shifts:
        s_start, s_end = shift_to_tuple(s)
        overlap_start = max(s_start, target_start)
        overlap_end = min(s_end, target_end)

        if overlap_start < overlap_end:
            overlap_duration = (overlap_end - overlap_start).total_seconds() / 3600
            coverage_by_person[person] = coverage_by_person.get(person, 0) + overlap_duration

    covered_people = set()
    for person, covered_hours in coverage_by_person.items():
        uncovered_hours = target_duration - covered_hours
        if uncovered_hours < 3:
            covered_people.add(person)

    return len(covered_people)

# ===== 生成班表 =====
if st.button("生成班表"):
    schedule = {p:{} for p in staff}
    staff_counts = {p:0 for p in staff}
    weekly_days = {p:{} for p in staff}

    remaining_demand = {d:{} for d in date_range}
    for d in date_range:
        for shift, info in st.session_state.shifts.items():
            remaining_demand[d][shift] = info["count"]

    daily_assigned = {d: [] for d in date_range}

    # 普通員工排班
    for d in date_range:
        week_index = d.isocalendar()[1]
        date_str = f"{d.strftime('%Y-%m-%d')}{weekday_bracket(d)}"
        sorted_shifts = sorted(st.session_state.shifts.items(), key=lambda x: -shift_hours(x[0]))

        for shift, info in sorted_shifts:
          covered = get_covered_count(shift, daily_assigned[d])
          if covered >= remaining_demand[d][shift]:
              continue

          actual_remaining = remaining_demand[d][shift] - covered

          for p in staff:
              if actual_remaining <= 0:
                  break  # 人數需求已滿
              if fill_in_staff[p]:
                  continue
              if shift not in availability.get(p, list(st.session_state.shifts.keys())):
                  continue
              if date_str in unavailable_days.get(p, []):
                  continue
              if max_days_per_week[p] is not None and weekly_days[p].get(week_index, 0) >= max_days_per_week[p]:
                  continue
              if len(schedule[p].get(date_str, [])) >= 1:
                  continue

              # 安排該員工
              schedule[p].setdefault(date_str, []).append(shift)
              staff_counts[p] += 1
              weekly_days[p][week_index] = weekly_days[p].get(week_index, 0) + 1
              remaining_demand[d][shift] -= 1
              actual_remaining -= 1
              daily_assigned[d].append((shift, p))

    # 填補空缺的人排固定班別
    for d in date_range:
        date_str = f"{d.strftime('%Y-%m-%d')}{weekday_bracket(d)}"
        for shift in st.session_state.fixed_shifts:
            target_count = st.session_state.fixed_shifts[shift]["count"]
            # 重新計算目前已覆蓋人數
            covered = get_covered_count(shift, daily_assigned[d])
            remaining = target_count - covered

            if remaining <= 0:
                continue

            for p in staff:
                if not fill_in_staff[p]:
                    continue
                if date_str in unavailable_days.get(p, []):
                    continue

                # 檢查這個人今天有無時間重疊班別
                existing_shifts = schedule[p].get(date_str, [])
                s_start, s_end = shift_to_tuple(shift)
                conflict = False
                for ex_shift in existing_shifts:
                    ex_start, ex_end = shift_to_tuple(ex_shift)
                    if max(s_start, ex_start) < min(s_end, ex_end):
                        conflict = True
                        break
                if conflict:
                    continue

                # 排班
                schedule[p].setdefault(date_str, []).append(shift)
                staff_counts[p] += 1
                remaining_demand[d][shift] -= 1
                daily_assigned[d].append((shift, p))

                # 每次安排後再重新檢查是否滿足班別人數
                covered = get_covered_count(shift, daily_assigned[d])
                if covered >= target_count:
                    break

        # 合併當天班別顯示（for 視覺簡潔）
        for p in staff:
            if date_str in schedule[p]:
                schedule[p][date_str] = ["/".join(schedule[p][date_str])]

    # ===== 生成表格 =====
    df_table = pd.DataFrame(index=staff, columns=[f"{d.strftime('%Y-%m-%d')}{weekday_bracket(d)}" for d in date_range])
    for p in staff:
        for date_str in df_table.columns:
            if date_str in unavailable_days.get(p,[]):
                df_table.loc[p,date_str] = "✖"
            elif date_str in schedule[p]:
                df_table.loc[p,date_str] = "/".join(schedule[p][date_str])
            else:
                df_table.loc[p,date_str] = "休"

    def style_cell(val):
        if val=="✖":
            return "color:red; font-weight:bold; text-align:center"
        elif val=="休":
            return "font-weight:bold; text-align:center"
        else:
            return "text-align:center"

    st.subheader("🗓 排班表")
    st.dataframe(df_table.style.applymap(style_cell))

    # ===== 統計表 =====
    stats_rows = []
    for p in staff:
        total_hours = 0
        for date_str, shifts in schedule[p].items():
            for shift in shifts:
                # shift 可能是 "08:00-11:00/11:00-16:30"
                parts = shift.split("/")
                for part in parts:
                    total_hours += shift_hours(part)
        stats_rows.append([p, staff_counts[p], total_hours])

    df_stats = pd.DataFrame(stats_rows, columns=["人員", "班次", "時數"])
    st.subheader("📊 人員統計")
    st.dataframe(df_stats)

    # ===== 下載 Excel =====
    file_name = f"{start_date.strftime('%Y-%m-%d')}～{end_date.strftime('%Y-%m-%d')} 排班表.xlsx"

    with pd.ExcelWriter("schedule.xlsx") as writer:
        df_table.to_excel(writer, sheet_name="班表")
        df_stats.to_excel(writer, sheet_name="統計表", index=False)

    with open("schedule.xlsx", "rb") as f:
        st.download_button(
            label="📥 下載班表",
            data=f,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
