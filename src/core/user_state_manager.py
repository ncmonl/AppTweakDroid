import os
import json
from typing import Any, Dict


class UserStateManager:
	"""负责保存/加载用户最近使用与上次成功的证书信息"""

	def __init__(self, state_file: str = "last_paths.json") -> None:
		self.state_file = state_file

	def load(self) -> Dict[str, Any]:
		try:
			if os.path.exists(self.state_file):
				with open(self.state_file, "r", encoding="utf-8") as f:
					return json.load(f) or {}
			return {}
		except Exception:
			return {}

	def save(self, data: Dict[str, Any]) -> None:
		try:
			with open(self.state_file, "w", encoding="utf-8") as f:
				json.dump(data or {}, f, ensure_ascii=False, indent=4)
		except Exception:
			pass

	def update_fields(self, updates: Dict[str, Any]) -> None:
		data = self.load()
		data.update(updates or {})
		self.save(data)

	def save_last_success_cert(self, cert_path: str, cert_password: str, key_alias: str, key_password: str) -> None:
		data = self.load()
		data['cert_path'] = cert_path
		data['cert_password'] = cert_password
		data['key_alias'] = key_alias
		data['key_password'] = key_password
		data['last_success_cert'] = {
			'cert_path': cert_path,
			'cert_password': cert_password,
			'key_alias': key_alias,
			'key_password': key_password,
		}
		self.save(data)

	def get_last_paths(self) -> Dict[str, Any]:
		"""返回 last_paths.json 的内容（可能为空字典）"""
		return self.load()

	def get_effective_certificate(self) -> Dict[str, Any]:
		"""基于保存的数据，返回应当优先使用的证书信息

		优先级：last_success_cert（且证书路径存在）> 普通存储字段（且证书路径存在）
		返回字段：{'cert_path','cert_password','key_password','key_alias','source'}，若不存在则为空字符串
		"""
		data = self.load()
		result = {
			'cert_path': '',
			'cert_password': '',
			'key_password': '',
			'key_alias': '',
			'source': 'none',
		}

		last_success = (data.get('last_success_cert') or {}) if isinstance(data, dict) else {}
		if last_success:
			p = last_success.get('cert_path') or ''
			if p and os.path.exists(p):
				result['cert_path'] = p
				result['cert_password'] = last_success.get('cert_password') or ''
				result['key_password'] = last_success.get('key_password') or ''
				result['key_alias'] = last_success.get('key_alias') or ''
				result['source'] = 'last_success'
				return result

		# fallback 到常规字段
		p2 = (data.get('cert_path') or '') if isinstance(data, dict) else ''
		if p2 and os.path.exists(p2):
			result['cert_path'] = p2
			result['cert_password'] = (data.get('cert_password') or '') if isinstance(data, dict) else ''
			result['key_password'] = (data.get('key_password') or '') if isinstance(data, dict) else ''
			result['key_alias'] = (data.get('key_alias') or '') if isinstance(data, dict) else ''
			result['source'] = 'regular'
		return result

	def should_auto_load_aliases(self, cert_path: str, cert_password: str) -> bool:
		"""是否应触发自动读取别名"""
		return bool(cert_path and cert_path.strip() and os.path.exists(cert_path) and cert_password and cert_password.strip())

	def get_preferred_alias_for_startup(self, alias_list):
		"""在启动场景下，从状态中选择更合适的别名

		返回 (alias, messages)
		- alias: 选择的别名（可能为空字符串）
		- messages: 供 UI 显示的提示
		"""
		messages = []
		alias = ''
		if not alias_list:
			return alias, messages

		data = self.load()
		preferred = ''
		last_success = (data.get('last_success_cert') or {}) if isinstance(data, dict) else {}
		if last_success and last_success.get('key_alias'):
			preferred = last_success.get('key_alias') or ''
			if preferred in alias_list:
				alias = preferred
				messages.append(f"已恢复上次的密钥别名：{alias}")
				return alias, messages

		# fallback 到常规字段
		preferred = (data.get('key_alias') or '') if isinstance(data, dict) else ''
		if preferred and preferred in alias_list:
			alias = preferred
			messages.append(f"已恢复上次的密钥别名：{alias}")
			return alias, messages

		# 最后选择第一项
		alias = alias_list[0]
		messages.append(f"已自动选择密钥别名：{alias}")
		return alias, messages

	def persist_key_alias(self, alias: str) -> None:
		if not alias:
			return
		self.update_fields({'key_alias': alias})


