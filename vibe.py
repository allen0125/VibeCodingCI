import subprocess
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
import logging
from dotenv import load_dotenv

# 优先加载 .env 文件中的环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Vibe:
    """Vibe 类 - 使用 Aider 对 Python 项目进行编码"""
    
    def __init__(self, project_path: str, aider_path: Optional[str] = None):
        """
        初始化 Vibe 实例
        
        Args:
            project_path: Python 项目文件夹路径
            aider_path: Aider 可执行文件路径，如果为 None 则使用系统 PATH 中的 aider
        """
        self.project_path = Path(project_path).resolve()
        self.aider_path = aider_path or "aider"
        
        # 验证项目路径
        if not self.project_path.exists():
            raise ValueError(f"项目路径不存在: {self.project_path}")
        
        if not self.project_path.is_dir():
            raise ValueError(f"项目路径不是文件夹: {self.project_path}")
        
        # 验证 Aider 是否可用
        self._check_aider_available()
    
    def _check_aider_available(self):
        """检查 Aider 是否可用"""
        try:
            result = subprocess.run(
                [self.aider_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError(f"Aider 不可用: {result.stderr}")
            logger.info(f"Aider 版本: {result.stdout.strip()}")
        except FileNotFoundError:
            raise RuntimeError(f"找不到 Aider 可执行文件: {self.aider_path}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Aider 启动超时")
    
    def code(self, requirements: str, files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        使用 Aider 对项目进行编码
        
        Args:
            requirements: 编码需求描述
            files: 要处理的文件列表，如果为 None 则处理所有 Python 文件
        
        Returns:
            包含执行结果的字典
        """
        try:
            # 构建 Aider 命令
            cmd = [self.aider_path]
            
            # 添加文件参数
            if files:
                for file_path in files:
                    full_path = self.project_path / file_path
                    if full_path.exists():
                        cmd.append(str(full_path))
                    else:
                        logger.warning(f"文件不存在，跳过: {file_path}")
            else:
                # 自动发现 Python 文件
                python_files = self._discover_python_files()
                cmd.extend(python_files)
            
            # 添加需求作为消息
            cmd.extend(["--message", requirements])
            
            # 设置工作目录和环境变量
            env = os.environ.copy()
            env["AIDER_WORK_DIR"] = str(self.project_path)
            
            # 从 .env 文件加载 aider 相关环境变量
            aider_api_key = os.getenv("AIDER_OPENAI_API_KEY")
            aider_api_base = os.getenv("AIDER_OPENAI_API_BASE")
            aider_model = os.getenv("AIDER_OPENAI_MODEL")
            
            if aider_api_key:
                env["OPENAI_API_KEY"] = aider_api_key
            if aider_api_base:
                env["OPENAI_API_BASE"] = aider_api_base
            if aider_model:
                env["AIDER_MODEL"] = aider_model
            
            logger.info(f"执行命令: {' '.join(cmd)}")
            logger.info(f"工作目录: {self.project_path}")
            logger.info(f"环境变量配置: {self.get_env_config()}")
            
            # 执行 Aider
            logger.info("🚀 开始执行 aider...")
            
            # 使用 Popen 来实时获取输出，并添加参数来避免交互式提示
            cmd.extend([
                "--no-show-model-warnings",
                "--yes",  # 自动确认所有提示
                "--no-check-update",  # 不检查更新
                "--no-analytics"  # 禁用分析
            ])
            
            process = subprocess.Popen(
                cmd,
                cwd=self.project_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,  # 添加 stdin 来处理交互式输入
                text=True,
                env=env,
                bufsize=1,
                universal_newlines=True
            )
            
            stdout_lines = []
            stderr_lines = []
            
            # 实时读取输出并处理交互式提示
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    output_line = output.strip()
                    logger.info(f"📤 aider: {output_line}")
                    stdout_lines.append(output)
                    
                    # 处理交互式提示
                    if "Open documentation url for more info?" in output_line:
                        logger.info("🤖 自动回答 'No' 以避免交互式提示")
                        process.stdin.write("N\n")
                        process.stdin.flush()
                    elif "Don't ask again" in output_line:
                        logger.info("🤖 自动回答 'D' 以不再询问")
                        process.stdin.write("D\n")
                        process.stdin.flush()
                    elif "Yes" in output_line and "No" in output_line and "Don't ask again" in output_line:
                        logger.info("🤖 自动回答 'N' 以跳过文档链接")
                        process.stdin.write("N\n")
                        process.stdin.flush()
            
            # 读取剩余输出
            remaining_stdout, remaining_stderr = process.communicate()
            if remaining_stdout:
                logger.info(f"📤 aider: {remaining_stdout}")
                stdout_lines.append(remaining_stdout)
            if remaining_stderr:
                logger.info(f"⚠️  aider: {remaining_stderr}")
                stderr_lines.append(remaining_stderr)
            
            returncode = process.returncode
            stdout = ''.join(stdout_lines)
            stderr = ''.join(stderr_lines)
            
            logger.info(f"✅ aider 执行完成，返回码: {returncode}")
            if stdout and not any(line.strip() for line in stdout_lines if line.strip()):
                logger.info(f"📤 aider 完整输出:\n{stdout}")
            if stderr and not any(line.strip() for line in stderr_lines if line.strip()):
                logger.info(f"⚠️  aider 完整错误输出:\n{stderr}")
            
            return {
                "success": returncode == 0,
                "returncode": returncode,
                "stdout": stdout,
                "stderr": stderr,
                "command": " ".join(cmd),
                "project_path": str(self.project_path)
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": "Aider 执行超时",
                "command": " ".join(cmd),
                "project_path": str(self.project_path)
            }
        except Exception as e:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"执行出错: {str(e)}",
                "command": " ".join(cmd),
                "project_path": str(self.project_path)
            }
    
    def _discover_python_files(self) -> List[str]:
        """发现项目中的 Python 文件"""
        python_files = []
        
        # 常见的 Python 文件模式
        patterns = ["*.py", "**/*.py"]
        
        for pattern in patterns:
            for file_path in self.project_path.glob(pattern):
                # 跳过 __pycache__ 和 .git 目录
                if "__pycache__" in str(file_path) or ".git" in str(file_path):
                    continue
                
                # 跳过虚拟环境目录
                if any(venv_dir in str(file_path) for venv_dir in ["venv", "env", ".venv", ".env"]):
                    continue
                
                python_files.append(str(file_path))
        
        logger.info(f"发现 {len(python_files)} 个 Python 文件")
        return python_files
    
    def get_project_info(self) -> Dict[str, Any]:
        """获取项目信息"""
        python_files = self._discover_python_files()
        
        return {
            "project_path": str(self.project_path),
            "python_files_count": len(python_files),
            "python_files": python_files,
            "aider_path": self.aider_path
        }
    
    def get_env_config(self) -> Dict[str, Any]:
        """获取环境变量配置信息"""
        return {
            "aider_openai_api_key": "已配置" if os.getenv("AIDER_OPENAI_API_KEY") else "未配置",
            "aider_openai_api_base": os.getenv("AIDER_OPENAI_API_BASE", "未配置"),
            "aider_openai_model": os.getenv("AIDER_OPENAI_MODEL", "未配置"),
            "openai_api_key": "已配置" if os.getenv("OPENAI_API_KEY") else "未配置",
            "openai_api_base": os.getenv("OPENAI_API_BASE", "未配置"),
            "aider_model": os.getenv("AIDER_MODEL", "未配置")
        }
    
    def interactive_mode(self, requirements: str, files: Optional[List[str]] = None):
        """
        交互模式 - 直接与 Aider 交互
        
        Args:
            requirements: 初始需求描述
            files: 要处理的文件列表
        """
        try:
            cmd = [self.aider_path]
            
            if files:
                for file_path in files:
                    full_path = self.project_path / file_path
                    if full_path.exists():
                        cmd.append(str(full_path))
            else:
                python_files = self._discover_python_files()
                cmd.extend(python_files)
            
            cmd.extend(["--message", requirements])
            
            # 添加参数来避免交互式提示
            cmd.extend([
                "--no-show-model-warnings",
                "--yes",  # 自动确认所有提示
                "--no-check-update",  # 不检查更新
                "--no-analytics"  # 禁用分析
            ])
            
            # 设置环境变量
            env = os.environ.copy()
            env["AIDER_WORK_DIR"] = str(self.project_path)
            
            # 从 .env 文件加载 aider 相关环境变量
            aider_api_key = os.getenv("AIDER_OPENAI_API_KEY")
            aider_api_base = os.getenv("AIDER_OPENAI_API_BASE")
            aider_model = os.getenv("AIDER_OPENAI_MODEL")
            
            if aider_api_key:
                env["OPENAI_API_KEY"] = aider_api_key
            if aider_api_base:
                env["OPENAI_API_BASE"] = aider_api_base
            if aider_model:
                env["AIDER_MODEL"] = aider_model
            
            logger.info(f"启动交互模式，命令: {' '.join(cmd)}")
            logger.info(f"工作目录: {self.project_path}")
            
            # 直接运行 Aider，不捕获输出
            subprocess.run(cmd, cwd=self.project_path, env=env)
            
        except KeyboardInterrupt:
            logger.info("用户中断了交互模式")
        except Exception as e:
            logger.error(f"交互模式出错: {str(e)}")


# 使用示例
if __name__ == "__main__":
    # 示例用法
    project_path = "/path/to/your/python/project"
    
    try:
        vibe = Vibe(project_path)
        
        # 获取项目信息
        info = vibe.get_project_info()
        print(f"项目信息: {json.dumps(info, indent=2, ensure_ascii=False)}")
        
        # 获取环境变量配置
        env_config = vibe.get_env_config()
        print(f"环境变量配置: {json.dumps(env_config, indent=2, ensure_ascii=False)}")
        
        # 执行编码任务
        requirements = "添加错误处理和日志记录"
        result = vibe.code(requirements)
        
        print(f"执行结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
    except Exception as e:
        print(f"错误: {str(e)}")
