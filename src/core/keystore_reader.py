import subprocess
import re
from typing import List, Tuple


class KeystoreReader:
	"""负责与 keytool 交互并解析别名输出的工具类"""

	def read_aliases(self, keystore_path: str, storepass: str) -> Tuple[List[str], List[str]]:
		"""读取 keystore/jks 文件中的 alias 列表

		返回 (aliases, messages)
		- aliases: 按顺序去重后的别名列表
		- messages: 过程中的提示/错误信息（供UI展示）
		"""
		messages: List[str] = []
		aliases: List[str] = []
		if not storepass or not storepass.strip():
			messages.append("错误：请先输入证书密码")
			return [], messages

		keytool_cmd = [
			"keytool", "-list",
			"-keystore", keystore_path,
			"-storepass", storepass,
		]

		# 运行 keytool，容错编码
		try:
			try:
				result = subprocess.run(keytool_cmd, capture_output=True, encoding='utf-8', errors='ignore')
				output = (result.stdout or "") + (result.stderr or "")
			except Exception:
				result = subprocess.run(keytool_cmd, capture_output=True, encoding='gbk', errors='ignore')
				output = (result.stdout or "") + (result.stderr or "")

			# 错误识别
			if "Keystore was tampered with, or password was incorrect" in output:
				messages.append("错误：密钥库密码不正确或密钥库文件被损坏")
				return [], messages
			if "java.io.IOException" in output:
				messages.append("错误：密钥库文件访问失败，请检查文件路径和权限")
				return [], messages
			if result.returncode not in (0, None):
				messages.append(f"错误：keytool命令执行失败，返回码：{result.returncode}")
				return [], messages

			# 解析别名
			for line in (output or "").splitlines():
				m = re.match(r"^别名名称: (.+)$", line)
				if m:
					self._append_unique(aliases, m.group(1).strip())
					continue
				m2 = re.match(r"^Alias name: (.+)$", line)
				if m2:
					self._append_unique(aliases, m2.group(1).strip())
					continue
				m3 = re.match(r"^([^,]+),\s*\d{4}年\d{1,2}月\d{1,2}日,\s*PrivateKeyEntry", line)
				if m3:
					self._append_unique(aliases, m3.group(1).strip())
					continue
				m4 = re.match(r"^([^,]+),\s*[A-Za-z]+\s+\d{1,2},\s+\d{4},\s*PrivateKeyEntry", line)
				if m4:
					self._append_unique(aliases, m4.group(1).strip())

			if not aliases:
				messages.append("警告：未找到任何密钥别名，请检查密钥库文件")

			# keytool 的迁移提示也原样透出给UI
			if "JKS 密钥库使用专用格式" in output:
				messages.append("Warning: 检测到JKS专用格式，建议迁移至PKCS12（可忽略）")

			return aliases, messages
		except Exception as e:
			messages.append(f"读取证书别名失败: {str(e)}")
			return [], messages

	@staticmethod
	def _append_unique(items: List[str], item: str) -> None:
		if item and item not in items:
			items.append(item)


