import subprocess

def set_env_var(name, value):
    try:
        # 先尝试设置系统级环境变量
        subprocess.run(['setx', name, value, '/M'], check=True, shell=True)
        print(f"Successfully set system environment variable {name} to {value}")
    except subprocess.CalledProcessError:
        try:
            # 如果系统级失败，尝试设置用户级环境变量
            subprocess.run(['setx', name, value], check=True, shell=True)
            print(f"Successfully set user environment variable {name} to {value} (system-level failed, possibly due to lack of admin privileges)")
        except subprocess.CalledProcessError as e:
            print(f"Failed to set {name}: {e}")

# 设置指定的环境变量
set_env_var('DEFAULT_SMTP_PASSWORD', 'Ky.741953')
set_env_var('DEFAULT_SMTP_PASS', 'vohqlhjgjebibbjg')
