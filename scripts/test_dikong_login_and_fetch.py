"""Simple Dikong API smoke tests.

Usage:
1) Edit constants at the top.
2) Run: python scripts/test_dikong_login_and_fetch.py
3) In main(), comment out any API test you do not want to run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


# -----------------------------
# Config constants (edit here)
# -----------------------------
BASE_URL = "http://61.169.171.82:50001"
ACCOUNT = "admin"
PASSWORD = "1qazXSW@4321"
TOKEN_NAME = "accessToken"
REQUEST_TIMEOUT = 20

SAVE_DIR_PATH = "docs/FlyReport/dikong-resp-api"

# -----------------------------
# API paths
# -----------------------------
LOGIN_PATH = "/system/user/login"
DEPT_LIST_PATH = "/system/dept/list"  # 部门列表，有部门关系， levelType不对，三四级有问题
DEPT_TREE_PATH = "/system/dept/deptTreeSelect"  # 部门树
USER_PAGE_PATH = "/system/user/page"
USER_INFO_PATH = "/system/user/info"
ROLE_INFO_PATH = "/system/role/info"  # 角色信息获取接口
ROLE_DEPT_TREE_PATH = "/system/dept/roleDeptTreeSelect"  # 获取角色部门树选择数据, role对应的可获取的部门吗？目前返回肯定不是想要的？TODO

MISSION_FLIGHT_PATH = "/api/device/missions/getFlyStatis"
FLIGHT_TASK_CALENDAR_OVERVIEW_PATH = "/api/device/flight-task/calendar/overview"  # 飞行任务日历概览，包含飞行统计数据

FLIGHT_JOB_LOG_LIST_PATH = "/api/device/job/log/list"  # 飞行历史接口
FLIGHT_JOB_LOG_DETAIL_PATH = "/api/device/job/log/"  # 飞行历史详情接口
JOB_LOG_EXPORT_PATH = "/api/device/job/log/export"  # 飞行历史导出接口

DRONE_BOUND_PATH = "/api/device/devices/manage/drone/bound"  # 获取已绑定无人机设备列表

WARN_STATIC_PATH = "/api/device/missions/getWarnStatic"  # 获取警告统计, 间接获取算法
ROUTE_LIST_PATH = "/api/device/route/list"  # 获取路线列表, 有场景，唯一获取，然后和AI算法组装


PIC_LIST_PATH = "/api/device/achs/pics"  # 获取图片列表
STORAGE_STATS_PATH = "/api/device/achs/storage/stats"
MEDIA_STATS_PATH = "/api/device/missions/getMediaStatic"  # 获取媒体统计, 包括图片和视频的数量、大小等，间接获取AI算法识别的结果
VIDEO_LIST_PATH = "/api/device/achs/videos"  # 获取视频列表, 目前看这个接口没有什么用，返回的都是空的

def _full_url(path: str) -> str:
	return f"{BASE_URL.rstrip('/')}{path}"


def _print_response(label: str, resp: requests.Response) -> None:
	print("=" * 80)
	print(label)
	print(f"HTTP {resp.status_code}")
	try:
		payload = resp.json()
		print(json.dumps(payload, ensure_ascii=False, indent=2))
	except ValueError:
		print(resp.text)


def _extract_token(login_json: dict[str, Any]):
	# Accept common token field names from different backend shapes.
	data = login_json.get("data", {})
	return data.get(TOKEN_NAME, "")


def login_get_token() -> str:
	"""Login with account/password and return back-token."""
	payload = {
		"account": ACCOUNT,
		"password": PASSWORD
	}
	headers = {"Content-Type": "application/json"}
	resp = requests.post(
		_full_url(LOGIN_PATH),
		json=payload,
		headers=headers,
		timeout=REQUEST_TIMEOUT,
	)
	_print_response("[LOGIN] /system/user/login", resp)
	resp.raise_for_status()

	login_json = resp.json()
	token = _extract_token(login_json)
	print(f"Token acquired, length={len(token)}")
	return token


def test_dept_list(token: str) -> None:
	"""Test department list query: GET /system/dept/list."""
	headers = {"back-token": token}
	resp = requests.get(
		_full_url(DEPT_LIST_PATH),
		headers=headers,
		timeout=REQUEST_TIMEOUT,
	)
	payload = resp.json()
	with open(os.path.join(SAVE_DIR_PATH, "dept_list.json"), "w", encoding="utf-8") as f:
		json.dump(payload, f, ensure_ascii=False, indent=2)


def get_dept_tree(token: str) -> None:
	"""Test department tree query: GET /system/dept/tree."""
	headers = {"back-token": token}
	resp = requests.get(
		_full_url(DEPT_TREE_PATH),
		headers=headers,
		timeout=REQUEST_TIMEOUT,
	)
	payload = resp.json()
	with open(os.path.join(SAVE_DIR_PATH, "dept_tree.json"), "w", encoding="utf-8") as f:
		json.dump(payload, f, ensure_ascii=False, indent=2)

def test_user_page(token: str) -> None:
	"""Test user info list query: GET /system/user/page."""
	headers = {"back-token": token}
	params = {
		"pageNum": 1,
		"pageSize": 20,
	}
	resp = requests.get(
		_full_url(USER_PAGE_PATH),
		headers=headers,
		params=params,
		timeout=REQUEST_TIMEOUT,
	)
	payload = resp.json()
	with open(os.path.join(SAVE_DIR_PATH, "user_page.json"), "w", encoding="utf-8") as f:
		json.dump(payload, f, ensure_ascii=False, indent=2)

def test_mission_flight_stat(token: str) -> None:
	"""Test mission flight stat query: GET /mission/flight/stat."""
	headers = {"back-token": token}
	params = {
		# "deptId": 381,
		"startdate": "2025-12-01",
		"enddate": "2026-12-31",
	}
	resp = requests.get(
		_full_url(MISSION_FLIGHT_PATH),
		headers=headers,
		params=params,
		timeout=REQUEST_TIMEOUT,
	)
	payload = resp.json()
	with open(os.path.join(SAVE_DIR_PATH, "mission_flight_stat.json"), "w", encoding="utf-8") as f:
		json.dump(payload, f, ensure_ascii=False, indent=2)

def test_flight_calendar_stat(token: str) -> None:
	"""Test flight calendar stat query: GET /api/device/flight-task/calendar/overview."""
	headers = {"back-token": token}
	params = {
		"year": 2026,
		"month": 4,
	}
	resp = requests.get(
		_full_url(FLIGHT_TASK_CALENDAR_OVERVIEW_PATH),
		headers=headers,
		params=params,
		timeout=REQUEST_TIMEOUT,
	)
	payload = resp.json()
	with open(os.path.join(SAVE_DIR_PATH, "flight_calendar_stat.json"), "w", encoding="utf-8") as f:
		json.dump(payload, f, ensure_ascii=False, indent=2)

def get_flight_job_log_list(token: str) -> None:
	# 获取部门的飞行历史包括任务包括飞行时间
	"""
	type（任务类型，t_missions.type）
	值	名称	含义
	0	DRONE	无人机任务
	1	DOCK_DRONE_ONCE	机巢单次
	2	DOCK_DRONE_ONCE_TIMER	机巢单次定时
	3	DOCK_DRONE_REPEAT_TIMER	机巢定时重复

	status（任务日志状态，sys_job_log.status）
	值	名称	含义
	0	PREPARE	待机准备
	1	PROGRESS	进行中
	2	SUCCESS	已完成
	3	CANCLE	已取消（拼写如此）
	4	FAILED	已失败
	"""
	"""Test flight job log list query: GET /api/device/job/log/list."""
	headers = {"back-token": token}

	params = {
		# "name": "",
		# "type": 1,
		# "status": 4, # 状态 0 待机准备,1 进行中,2 已结束,3 取消,4 异常,5 暂停
		"pageNum": 1,
		"pageSize": 2000,
		"startTime": "2026-01-09 00:00:00",
		"endTime": "2026-04-09 23:59:59",
	}
	resp = requests.get(
		_full_url(FLIGHT_JOB_LOG_LIST_PATH),
		headers=headers,
		params=params,
		timeout=REQUEST_TIMEOUT,
	)
	payload = resp.json()
	with open(os.path.join(SAVE_DIR_PATH, "flight_job_log_list.json"), "w", encoding="utf-8") as f:
		json.dump(payload, f, ensure_ascii=False, indent=2)

def get_flight_job_log_detail(token: str, job_log_id: str) -> None:
	"""Test flight job log detail query: GET /api/device/job/log/{id}."""
	headers = {"back-token": token}
	resp = requests.get(
		_full_url(f"{FLIGHT_JOB_LOG_DETAIL_PATH}{job_log_id}"),
		headers=headers,
		timeout=REQUEST_TIMEOUT,
	)
	payload = resp.json()
	with open(os.path.join(SAVE_DIR_PATH, f"flight_job_log_detail_{job_log_id}.json"), "w", encoding="utf-8") as f:
		json.dump(payload, f, ensure_ascii=False, indent=2)

def export_flight_job_log(token: str) -> None:
	"""Test flight job log export: GET /api/device/job/log/export."""
	headers = {"back-token": token}
	body = {
        "beginTime": "2026-01-01 00:00:00",
        "endTime": "2026-04-24 23:59:59",
        # 也可以按需带这些字段：
        # "jobLogId": "123456",
        # "jobLogNo": "JL202604240001",
        # "jobId": 1001,
        # "jobGroup": "DEFAULT",
        # "startTime": "2026-04-24 10:00:00",
        # "stopTime": "2026-04-24 11:00:00",
    }
	resp = requests.post(
        _full_url(JOB_LOG_EXPORT_PATH),
        headers=headers,
        json=body,
        timeout=REQUEST_TIMEOUT,
        stream=True,
    )

	resp.raise_for_status()

	content_type = resp.headers.get("Content-Type", "")
	disposition = resp.headers.get("Content-Disposition", "")
	print(f"Content-Type: {content_type}")
	print(f"Content-Disposition: {disposition}")

	if "application/json" in content_type:
		print("server returned json instead of file:")
		print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
		return

	file_name = "job_log_export.xlsx"
	if "filename=" in disposition:
		file_name = disposition.split("filename=")[-1].strip().strip('"')

	output_path = Path(file_name)
	with output_path.open("wb") as f:
		for chunk in resp.iter_content(chunk_size=8192):
			if chunk:
				f.write(chunk)

	print(f"export saved to: {output_path.resolve()}")

def get_drone_bound(token: str) -> None:
	"""Test drone bound query: GET /api/devices/manage/drone/bound."""
	headers = {"back-token": token}
	params = {
		"pageNum": 1,
		"pageSize": 5,
		# "user.deptId": 381  # TODO 这个deptId是必须的吗？如果是的话，说明接口权限控制是基于部门的？需要确认,
	}
	resp = requests.get(
		_full_url(DRONE_BOUND_PATH),
		headers=headers,
		params=params,
		timeout=REQUEST_TIMEOUT,
	)
	with open(os.path.join(SAVE_DIR_PATH, "drone_bound.json"), "w", encoding="utf-8") as f:
		json.dump(resp.json(), f, ensure_ascii=False, indent=2)

def get_pic_list(token: str) -> None:
	"""Test picture list query: GET /api/device/pics/getPicList."""
	headers = {"back-token": token}
	params = {
		"pageNum": 1,
		"pageSize": 20,
	}
	resp = requests.get(
		_full_url(PIC_LIST_PATH),
		headers=headers,
		params=params,
		timeout=REQUEST_TIMEOUT,
	)
	with open(os.path.join(SAVE_DIR_PATH, "pic_list.json"), "w", encoding="utf-8") as f:
		json.dump(resp.json(), f, ensure_ascii=False, indent=2)

def get_user_info(token: str) -> None:
	headers = {"back-token": token}
	resp = requests.get(
		_full_url(USER_INFO_PATH),
		headers=headers,
		timeout=REQUEST_TIMEOUT,
	)
	with open(os.path.join(SAVE_DIR_PATH, "user_info.json"), "w", encoding="utf-8") as f:
		json.dump(resp.json(), f, ensure_ascii=False, indent=2)

def get_role_info(token: str) -> None:
	headers = {"back-token": token}
	params = {
		"roleId": "3"
	}
	resp = requests.get(
		_full_url(ROLE_INFO_PATH),
		headers=headers,
		params=params,
		timeout=REQUEST_TIMEOUT,
	)
	with open(os.path.join(SAVE_DIR_PATH, "role_info.json"), "w", encoding="utf-8") as f:
		json.dump(resp.json(), f, ensure_ascii=False, indent=2)

def get_role_dept_tree(token: str) -> None:
	headers = {"back-token": token}
	params = {
		"roleId": "3"
	}
	resp = requests.get(
		_full_url(ROLE_DEPT_TREE_PATH),
		headers=headers,
		params=params,
		timeout=REQUEST_TIMEOUT,
	)
	with open(os.path.join(SAVE_DIR_PATH, "role_dept_tree.json"), "w", encoding="utf-8") as f:
		json.dump(resp.json(), f, ensure_ascii=False, indent=2)

def get_warn_static(token: str) -> None:
	# 识别总次数、
	headers = {"back-token": token}
	params = {
		"deptId": 380,
		"startdate": "2026-04-01",
		"enddate": "2026-04-30",
		"pageNum": 1,
		"pageSize": 999999,
	}
	resp = requests.get(
		_full_url(WARN_STATIC_PATH),
		headers=headers,
		params=params,
		timeout=REQUEST_TIMEOUT,
	)
	with open(os.path.join(SAVE_DIR_PATH, "warn_static.json"), "w", encoding="utf-8") as f:
		json.dump(resp.json(), f, ensure_ascii=False, indent=2)

def get_route_list(token: str) -> None:
	headers = {"back-token": token}
	params = {
		# "pageNum": 1,
		# "pageSize": 20,
		# "deptidsTag": "381",  # TODO , 分割
	}
	resp = requests.get(
		_full_url(ROUTE_LIST_PATH),
		headers=headers,
		params=params,
		timeout=REQUEST_TIMEOUT,
	)
	with open(os.path.join(SAVE_DIR_PATH, "route_list.json"), "w", encoding="utf-8") as f:
		json.dump(resp.json(), f, ensure_ascii=False, indent=2)

def get_storage_stats(token: str) -> None:
	headers = {"back-token": token}
	resp = requests.get(
		_full_url(STORAGE_STATS_PATH),
		headers=headers,
		timeout=REQUEST_TIMEOUT,
	)
	with open(os.path.join(SAVE_DIR_PATH, "storage_stats.json"), "w", encoding="utf-8") as f:
		json.dump(resp.json(), f, ensure_ascii=False, indent=2)

def get_media_stats(token: str) -> None:
	headers = {"back-token": token}
	params = {
		# "deptId": 381,
		"startdate": "2026-01-01",
		"enddate": "2026-04-30",
	}
	resp = requests.get(
		_full_url(MEDIA_STATS_PATH),
		headers=headers,
		params=params,
		timeout=REQUEST_TIMEOUT,
	)
	with open(os.path.join(SAVE_DIR_PATH, "media_stats.json"), "w", encoding="utf-8") as f:
		json.dump(resp.json(), f, ensure_ascii=False, indent=2)

def get_video_list(token: str) -> None:
	headers = {"back-token": token}
	params = {
		"pageNum": 1,
		"pageSize": 20,
	}
	resp = requests.get(
		_full_url(VIDEO_LIST_PATH),
		headers=headers,
		params=params,
		timeout=REQUEST_TIMEOUT,
	)
	with open(os.path.join(SAVE_DIR_PATH, "video_list.json"), "w", encoding="utf-8") as f:
		json.dump(resp.json(), f, ensure_ascii=False, indent=2)


def main() -> None:
	token = login_get_token()
	if not token:
		print("Failed to acquire token, aborting API tests.")
		return

	# Keep the calls you want, comment out those you do not want to test.
	# test_dept_list(token)
	# get_dept_tree(token)
	# test_user_page(token)
	# test_mission_flight_stat(token)
	# test_flight_calendar_stat(token)
	# get_flight_job_log_list(token)
	# get_flight_job_log_detail(token, job_log_id="3dd476ea-88c6-4288-9e00-d2e92bd48680")
	# get_drone_bound(token)
	# export_flight_job_log(token)
	# get_pic_list(token)
	# get_user_info(token)
	# get_role_info(token)
	# get_role_dept_tree(token)
	get_warn_static(token)
	# get_route_list(token)
	# get_storage_stats(token)
	# get_media_stats(token)
	# get_video_list(token)


if __name__ == "__main__":
	main()
