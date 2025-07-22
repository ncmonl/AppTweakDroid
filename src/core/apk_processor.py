from androguard.core.bytecodes.apk import APK
from lxml import etree
import os
import subprocess
import tempfile
import shutil

class ApkProcessor:
    def __init__(self, config_manager, logger=None):
        self.temp_dir = None
        self.config_manager = config_manager
        self.logger = logger or print  # Use provided logger or fallback to print
        self.tools_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))
        self.output_dir = os.path.abspath(self.config_manager.get_value('output_dir', 'output'))
        
        # 获取 Android SDK 路径
        self.android_home = os.getenv('ANDROID_HOME')
        if not self.android_home:
            raise EnvironmentError("未找到 ANDROID_HOME 环境变量，请先配置 Android SDK 路径")
        
        # 获取 build-tools 最新版本目录
        build_tools_dir = os.path.join(self.android_home, 'build-tools')
        if not os.path.exists(build_tools_dir):
            raise FileNotFoundError(f"未找到 build-tools 目录：{build_tools_dir}")
        
        # 使用 35.0.0 版本
        self.build_tools_dir = os.path.join(build_tools_dir, '35.0.0')
        if not os.path.exists(self.build_tools_dir):
            raise FileNotFoundError(f"未找到 build-tools 35.0.0 版本：{self.build_tools_dir}")
        
        # 确保输出目录存在
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _validate_apk_file(self, apk_path):
        """验证APK文件格式"""
        try:
            from zipfile import ZipFile
            with ZipFile(apk_path) as zf:
                return True
        except Exception as e:
            raise Exception(f"APK文件格式无效，请确保文件未损坏：{str(e)}")

    def process_apk(self, apk_path, cert_path, cert_password, key_alias, key_password, callback=None):
        """处理APK文件的主要方法"""
        try:
            self.logger(f"开始处理APK文件: {apk_path}")
            # 验证文件是否存在
            if not os.path.exists(apk_path):
                raise FileNotFoundError(f"找不到APK文件：{apk_path}")
            if not os.path.exists(cert_path):
                raise FileNotFoundError(f"找不到证书文件：{cert_path}")

            self.logger("正在验证APK文件格式...")
            # 验证APK文件格式
            self._validate_apk_file(apk_path)
            self.logger("APK文件格式验证通过")

            # 验证工具是否存在
            apktool_path = os.path.join(self.tools_dir, 'apktool.jar')
            if not os.path.exists(apktool_path):
                raise FileNotFoundError(f"找不到apktool工具：{apktool_path}")

            # 创建临时目录前，确保清理已存在的临时目录
            apk_base = os.path.splitext(os.path.basename(apk_path))[0]
            temp_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'temp'))
            if not os.path.exists(temp_root):
                os.makedirs(temp_root)
            temp_dir_path = os.path.join(temp_root, apk_base + '_work')
            if os.path.exists(temp_dir_path):
                self.logger(f"清理同名临时目录: {temp_dir_path}")
                shutil.rmtree(temp_dir_path)
            os.makedirs(temp_dir_path)
            self.temp_dir = temp_dir_path
            self.logger(f"创建临时工作目录: {self.temp_dir}")
            
            # 反编译APK
            self.logger("开始反编译APK文件...")
            self._decompile_apk(apk_path)
            self.logger("APK反编译完成")
            
            # 修改网络安全配置
            self.logger("开始修改网络安全配置...")
            self._modify_network_security_config()
            self.logger("网络安全配置修改完成")
            
            # 根据配置决定是否添加可调试属性
            if self.config_manager.get_value('debuggable_enabled', False):
                self.logger("开始检查和修改 debuggable 属性...")
                self._modify_manifest()
                self.logger("debuggable 属性检查修改完成")
            
            # 重新打包APK
            self.logger("开始重新打包APK...")
            new_apk_path = self._repackage_apk(apk_path)
            self.logger(f"APK重打包完成: {new_apk_path}")
            
            # 如果启用了zipalign，在签名前进行优化
            if self.config_manager.get_value('zipalign_enabled', False):
                self.logger("正在进行zipalign优化...")
                self._zipalign_apk(new_apk_path)
                self.logger("zipalign优化完成")
            
            # 签名APK
            self.logger("开始对APK进行签名...")
            self._sign_apk(new_apk_path, cert_path, cert_password, key_alias, key_password)
            self.logger("APK签名完成")
            
            # 移动最终的APK到输出目录
            final_apk_name = os.path.basename(new_apk_path)
            output_path = os.path.join(self.output_dir, final_apk_name)
            shutil.move(new_apk_path, output_path)
            self.logger(f"已将处理完成的APK移动到输出目录: {output_path}")
            
            return True, "处理完成"
        except Exception as e:
            error_msg = f"处理失败: {str(e)}"
            self.logger(error_msg)
            return False, error_msg
        finally:
            # 清理临时文件
            self.cleanup()

    def _decompile_apk(self, apk_path):
        """使用apktool反编译APK"""
        apktool_path = os.path.join(self.tools_dir, 'apktool.jar')
        self.logger(f"使用apktool工具: {apktool_path}")
        result = subprocess.run(['java', '-jar', apktool_path, 'd', '-f', apk_path, '-o', self.temp_dir], 
                             capture_output=True, text=True)
        self.logger("apktool输出:")
        if result.stdout:
            self.logger(result.stdout)
        if result.stderr:
            self.logger("apktool错误输出:")
            self.logger(result.stderr)
        if result.returncode != 0:
            raise Exception(f"APK反编译失败: {result.stderr}")

    def _modify_network_security_config(self):
        """修改网络安全配置"""
        manifest_path = os.path.join(self.temp_dir, 'AndroidManifest.xml')
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"找不到AndroidManifest.xml文件：{manifest_path}")

        # 直接使用lxml解析XML文件
        tree = etree.parse(manifest_path)
        root = tree.getroot()
        
        # 获取网络安全配置文件路径
        network_config = root.get('{http://schemas.android.com/apk/res/android}networkSecurityConfig')
        
        if network_config:
            config_path = os.path.join(self.temp_dir, 'res', 'xml', 
                                     network_config.replace('@xml/', '') + '.xml')
            self._update_security_config(config_path)

    def _update_security_config(self, config_path):
        """更新安全配置文件"""
        if not os.path.exists(config_path):
            return
        
        tree = etree.parse(config_path)
        root = tree.getroot()
        
        # 添加信任用户证书配置
        trust_anchors = root.find('.//trust-anchors')
        if trust_anchors is None:
            base_config = root.find('.//base-config')
            if base_config is None:
                base_config = etree.SubElement(root, 'base-config')
            trust_anchors = etree.SubElement(base_config, 'trust-anchors')
        
        # 添加用户证书配置
        certificates = trust_anchors.findall('certificates')
        user_cert_exists = any(cert.get('source') == 'user' for cert in certificates)
        
        if not user_cert_exists:
            cert_elem = etree.SubElement(trust_anchors, 'certificates')
            cert_elem.set('source', 'user')
        
        # 保存修改后的配置
        tree.write(config_path, encoding='utf-8', xml_declaration=True)

    def _repackage_apk(self, apk_path):
        """重新打包APK"""
        # 获取原始APK文件名并添加_Trust后缀
        original_name = os.path.basename(apk_path)
        base_name = os.path.splitext(original_name)[0]
        output_name = f"{base_name}_Trust.apk"
        output_dir = os.path.dirname(apk_path)
        output_path = os.path.join(output_dir, output_name)

        apktool_path = os.path.join(self.tools_dir, 'apktool.jar')
        self.logger(f"使用apktool重新打包: {apktool_path}")
        result = subprocess.run(['java', '-jar', apktool_path, 'b', self.temp_dir, '-o', output_path], 
                             capture_output=True, text=True)
        self.logger("apktool打包输出:")
        if result.stdout:
            self.logger(result.stdout)
        if result.stderr:
            self.logger("apktool打包错误输出:")
            self.logger(result.stderr)
        if result.returncode != 0:
            raise Exception(f"APK重打包失败: {result.stderr}")
        return output_path

    def _zipalign_apk(self, apk_path):
        """对APK进行zipalign优化"""
        # 使用 Android SDK 中的 zipalign
        zipalign_name = 'zipalign.exe' if os.name == 'nt' else 'zipalign'
        zipalign_path = os.path.join(self.build_tools_dir, zipalign_name)
        
        if not os.path.exists(zipalign_path):
            raise FileNotFoundError(f"找不到zipalign工具：{zipalign_path}")
        
        aligned_apk = os.path.join(os.path.dirname(apk_path), 'aligned_' + os.path.basename(apk_path))
        
        result = subprocess.run([
            zipalign_path,
            '-v', '4',
            apk_path,
            aligned_apk
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Zipalign失败: {result.stderr}")
        
        # 替换原文件
        os.replace(aligned_apk, apk_path)

    def _sign_apk(self, apk_path, cert_path, cert_password, key_alias, key_password):
        """使用 apksigner 签名 APK"""
        self.logger(f"使用证书 {cert_path} 进行签名")
        
        # 使用 Android SDK 中的 apksigner
        apksigner_name = 'apksigner.bat' if os.name == 'nt' else 'apksigner'
        apksigner_path = os.path.join(self.build_tools_dir, apksigner_name)
        
        if not os.path.exists(apksigner_path):
            raise FileNotFoundError(f"找不到apksigner工具：{apksigner_path}")
        
        result = subprocess.run([
            apksigner_path, 'sign',
            '--v1-signing-enabled', 'true',
            '--v2-signing-enabled', 'true',
            '--ks', cert_path,
            '--ks-pass', f'pass:{cert_password}',
            '--ks-key-alias', key_alias,
            '--key-pass', f'pass:{key_password}',
            apk_path
        ], capture_output=True, text=True)
        
        self.logger("apksigner输出:")
        if result.stdout:
            self.logger(result.stdout)
        if result.stderr:
            self.logger("apksigner错误输出:")
            self.logger(result.stderr)
        if result.returncode != 0:
            raise Exception(f"APK签名失败: {result.stderr}")
        
        # 验证签名
        verify_result = subprocess.run([
            apksigner_path, 'verify',
            '--verbose',
            apk_path
        ], capture_output=True, text=True)
        
        if verify_result.returncode != 0:
            raise Exception(f"签名验证失败: {verify_result.stderr}")
        self.logger("签名验证通过")

    def _modify_manifest(self):
        """修改 AndroidManifest.xml，添加 debuggable 属性"""
        manifest_path = os.path.join(self.temp_dir, 'AndroidManifest.xml')
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"找不到AndroidManifest.xml文件：{manifest_path}")

        # 解析 AndroidManifest.xml
        tree = etree.parse(manifest_path)
        root = tree.getroot()
        
        # 查找 application 节点
        application = root.find('.//application')
        if application is None:
            raise Exception("未找到 application 节点")
        
        # 检查是否已经有 debuggable 属性
        android_ns = '{http://schemas.android.com/apk/res/android}'
        debuggable_attr = f'{android_ns}debuggable'
        
        if debuggable_attr not in application.attrib or application.attrib[debuggable_attr] != 'true':
            self.logger("添加 debuggable 属性")
            application.set(debuggable_attr, 'true')
            # 保存修改后的文件
            tree.write(manifest_path, encoding='utf-8', xml_declaration=True)
            self.logger("AndroidManifest.xml 修改完成")
        else:
            self.logger("已存在 debuggable=true 配置")

    def cleanup(self):
        """清理临时文件"""
        # if self.temp_dir and os.path.exists(self.temp_dir):
        #     try:
        #         shutil.rmtree(self.temp_dir)
        #         self.logger("临时文件清理完成")
        #     except Exception as e:
        #         self.logger(f"清理临时文件失败: {str(e)}")
