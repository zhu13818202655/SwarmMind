"""Simple Dikong API smoke tests.

Usage:
1) Edit constants at the top.
2) Run: python scripts/test_dikong_login_and_fetch.py
3) In main(), comment out any API test you do not want to run.
"""

from __future__ import annotations

import json
import os
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
PIC_LIST_PATH = "/api/device/achs/pics"  # 获取图片列表
# 所有用户
# 部门下用户


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
		"deptId": 381,
		"startdate": "2024-01-01",
		"enddate": "2026-12-31",
	}
	resp = requests.get(
		_full_url(MISSION_FLIGHT_PATH),
		headers=headers,
		# params=params,
		timeout=REQUEST_TIMEOUT,
	)
	payload = resp.json()
	with open(os.path.join(SAVE_DIR_PATH, "mission_flight_stat.json"), "w", encoding="utf-8") as f:
		json.dump(payload, f, ensure_ascii=False, indent=2)


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


def main() -> None:
	token = login_get_token()
	if not token:
		print("Failed to acquire token, aborting API tests.")
		return

	# Keep the calls you want, comment out those you do not want to test.
	# test_dept_list(token)
	# get_dept_tree(token)
	# test_user_page(token)
	test_mission_flight_stat(token)
	# get_pic_list(token)
	# get_user_info(token)
	# get_role_info(token)
	# get_role_dept_tree(token)


if __name__ == "__main__":
	main()
