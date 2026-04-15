
# builds gki kernel
import os
import subprocess
import sys
import json
import zipfile
import shutil
from collections import deque
import argparse
import glob

download_cache = "download_cache.json"
def load_download_cache():
    if os.path.exists(download_cache):
        with open(download_cache, "r") as f:
            return json.load(f)
    return {}
def save_download_cache(cache):
    with open(download_cache, "w") as f:
        json.dump(cache, f)
def download_file(url):
    if not url:
        raise ValueError("URL is empty")
    # check if the url is already in the cache
    #if url start with "file://", return the local file path
    if url.startswith("file://"):
        local_path = url[7:]
        if os.path.exists(local_path):
            return local_path
        else:
            raise ValueError(f"Local file {local_path} does not exist")
    cache = load_download_cache()
    if url in cache:
        print(f"Using cached file for {url}")
        return cache[url]
    random_string = os.urandom(8).hex()
    cache_file = f"{random_string}.cache"
    # create cache dir if it doesn't exist
    if not os.path.exists("cache"):
        os.makedirs("cache")
    cache_path = os.path.join("cache", cache_file)
    # download the file to cache using aria2c or curl
    try:
        subprocess.run(["aria2c", "-x", "16", "-s", "16", "-o", cache_path, url], check=True)
    except subprocess.CalledProcessError:
        subprocess.run(["curl", "-L", url, "-o", cache_path], check=True)
    #return the path to the cached file
    cache[url] = cache_path
    save_download_cache(cache)
    return cache_path

def load_config(config_file):
    """{
    "version": "6.12.23",
    "description": "GKI",
    "arch": "arm64",
    "source": "https://github.com/cctv18/android_gki_kernel_common/archive/refs/heads/android16-6.12-2025-06.zip",
    "compiler":{
        "clang": "https://github.com/cctv18/oneplus_sm8650_toolchain/releases/download/LLVM-Clang19-r536225/clang-r536225.zip",
        "rustc": "https://github.com/cctv18/oneplus_sm8650_toolchain/releases/download/LLVM-Clang19-r536225/rust.zip",
        "build-tools": "https://github.com/cctv18/oneplus_sm8650_toolchain/releases/download/LLVM-Clang19-r536225/build-tools.zip"
    }
}"""
    with open(config_file, "r") as f:
        return json.load(f)
def unzip_file(zip_path, extract_to, folder_name):
    """
    使用系统 unzip 命令解压 zip 文件，保留文件权限。
    如果 zip 内只有一个顶层文件夹，则将其重命名为 folder_name。
    否则将所有内容解压到 extract_to/folder_name 目录下。
    """
    # 确保目标目录存在
    os.makedirs(extract_to, exist_ok=True)
    
    # 检查系统是否安装 unzip
    if not shutil.which("unzip"):
        raise RuntimeError("'unzip' Not found. Please install unzip (e.g., apt install unzip)")

    # 创建临时解压目录
    temp_extract = os.path.join(extract_to, '_temp_extract')
    os.makedirs(temp_extract, exist_ok=True)

    try:
        # 调用系统 unzip，-q 静默模式，-d 指定目标目录
        subprocess.run(["unzip", "-q", zip_path, "-d", temp_extract], check=True)

        # 获取顶层条目列表
        items = os.listdir(temp_extract)
        # 过滤掉可能的隐藏文件（如 .DS_Store）—— 保留显式条目
        items = [item for item in items if not item.startswith('.')] or items

        if len(items) == 1:
            # 只有一个顶层文件夹/文件
            src_path = os.path.join(temp_extract, items[0])
            dest_path = os.path.join(extract_to, folder_name)
            if os.path.isdir(src_path):
                # 如果是文件夹，直接移动并重命名
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.move(src_path, dest_path)
            else:
                # 如果顶层只有一个文件（罕见情况），仍创建文件夹并放入
                os.makedirs(dest_path, exist_ok=True)
                shutil.move(src_path, os.path.join(dest_path, items[0]))
        else:
            # 多个顶层条目，统一放入 folder_name 目录
            dest_dir = os.path.join(extract_to, folder_name)
            if os.path.exists(dest_dir):
                shutil.rmtree(dest_dir)
            os.makedirs(dest_dir, exist_ok=True)
            for item in items:
                shutil.move(os.path.join(temp_extract, item), os.path.join(dest_dir, item))

    finally:
        # 清理临时目录
        if os.path.exists(temp_extract):
            shutil.rmtree(temp_extract)
def remove_dirty(workspace_dir):
    """
    模拟以下 bash 操作：
    for f in common/scripts/setlocalversion; do
      sed -i 's/ -dirty//g' "$f"
      sed -i '$i res=$(echo "$res" | sed '\''s/-dirty//g'\'')' "$f"
    done
    """
    file_path = os.path.join(workspace_dir, "common/scripts/setlocalversion")
    if not os.path.isfile(file_path):
        # 文件不存在时静默返回（可根据需要改为抛出异常）
        return

    # 读取所有行
    with open(file_path, "r") as f:
        lines = f.readlines()

    # 1) 替换所有 " -dirty" 为空（注意保留空格前的空格）
    new_lines = [line.replace(" -dirty", "") for line in lines]

    # 2) 在最后一行之前插入一行内容
    insert_line = 'res=$(echo "$res" | sed \'s/-dirty//g\')\n'
    if new_lines:
        # 插入位置：最后一行之前（即索引 len-1 处）
        new_lines.insert(len(new_lines) - 1, insert_line)
    else:
        # 文件原本为空，直接写入该行
        new_lines = [insert_line]

    # 写回文件
    with open(file_path, "w") as f:
        f.writelines(new_lines)

import os

def apply_kernel_suffix(root_dir, suffix=None):
    workspace = os.path.join(root_dir, "kernel_workspace")
    setlocalversion_path = os.path.join(workspace, "common/scripts/setlocalversion")
    defconfig_path = os.path.join(workspace, "common/arch/arm64/configs/gki_defconfig")
    if not suffix:
        return
    if os.path.isfile(setlocalversion_path):
        with open(setlocalversion_path, "r") as f:
            lines = f.readlines()

        # 删除所有 '${scm_version}'
        lines = [line.replace('${scm_version}', '') for line in lines]

        # 将最后一行中的 'echo "$res"' 替换为 'echo "-{suffix}"'
        if lines:
            last_line = lines[-1]
            new_last_line = last_line.replace('echo "$res"', f'echo "-{suffix}"')
            lines[-1] = new_last_line

        with open(setlocalversion_path, "w") as f:
            f.writelines(lines)
    else:
        print(f"Warning: {setlocalversion_path} not found")
    if os.path.isfile(defconfig_path):
        with open(defconfig_path, "r") as f:
            content = f.read()

        new_content = content.replace("-4k", f"-{suffix}")
        new_content += "\nCONFIG_LOCALVERSION_AUTO=n\n"

        with open(defconfig_path, "w") as f:
            f.write(new_content)
    else:
        print(f"Warning: {defconfig_path} not found")

    print("Finished applying kernel suffix.")

def check_version_compatibility(supported_versions, kernel_version):
    """
    检查 kernel_version 是否在 supported_versions 中。
    supported_versions 是一个字符串列表，kernel_version 是一个字符串。
    返回 True 如果兼容，否则返回 False。
    kernel 6.12.23 需要匹配 6.12 或 6.12.23
    """
    for version in supported_versions:
        if kernel_version.startswith(version):
            return True
    return False

def apply_patch(patch_file,allow_failure=False):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.run(["patch", "-p1", "-F", "3", "-i", patch_file], cwd=os.path.join(script_dir, "kernel_workspace/common"), check=True)
        print(f"Patch {patch_file} applied successfully.")
        return True
    except subprocess.CalledProcessError:
        if allow_failure:
            print(f"Warning: failed to apply patch {patch_file}, but continuing anyway...")
            return True
        else:
            print(f"Error: failed to apply patch {patch_file}.")
            return False
def append_defconfig(defconfig_append,mod_name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gki_defconfig = os.path.join(script_dir, "kernel_workspace/common/arch/arm64/configs/gki_defconfig")
    if os.path.isfile(gki_defconfig):
        with open(defconfig_append, "r") as f:
            append_content = f.read()
        with open(gki_defconfig, "a") as f:
            f.write("\n# Append from mod " + mod_name + "\n")
            f.write(append_content)
        print(f"Defconfig append from {defconfig_append} applied successfully.")
    else:
        print(f"Warning: gki_defconfig not found in workspace, skipping defconfig append from {defconfig_append}...")

def manual_mod(workspace_dir, mod_path, kconfig,allow_failure=False):
    # directly excute the setup.sh in the mod_path
    #run in the workspace_dir
    #export KERNEL_WORKSPACE MOD_PATH before excuting the script
    setup_script = os.path.join(mod_path, "setup.sh")
    if os.path.isfile(setup_script):
        print(f"Warning: setup.sh not found in {mod_path}, skipping manual mod...")
        env = os.environ.copy()
        script_dir = os.path.dirname(__file__)
        env["KERNEL_WORKSPACE"] = workspace_dir
        env["SCRIPT_DIR"] = os.path.dirname(__file__)
        env["MOD_PATH"] = mod_path
        env["ANDROID_VERSION"] = kconfig.get("android_version")
        env["KERNEL_VERSION"] = kconfig.get("kernel_version")
        env["DOWNLOAD_FILE"] = os.path.join(script_dir, "kernelbuild.py") + " --download"
        env["APPLY_PATCH"] = os.path.join(script_dir, "kernelbuild.py") + " --applypatch"
        return_code = subprocess.run(["bash", setup_script], cwd=workspace_dir, env=env, check=True)
        if return_code.returncode != 0:
            print(f"Warning: failed to apply manual mod {mod_path}, skipping...")
            return False
    patch_file = os.path.join(mod_path, "patch.diff")
    if os.path.isfile(patch_file):
        apply_patch(patch_file, allow_failure=allow_failure)
    defconfig_append=os.path.join(mod_path, "defconfig_append")
    if os.path.isfile(defconfig_append):
        append_defconfig(defconfig_append, mod_name=kconfig.get("name"))
    print(f"Manual mod {mod_path} applied successfully.")
    return True
def post_mod(workspace_dir, mod_path, kconfig):
    # directly excute the post.sh in the mod_path
    #run in the workspace_dir
    #export KERNEL_WORKSPACE MOD_PATH before excuting the script
    setup_script = os.path.join(mod_path, "post.sh")
    if not os.path.isfile(setup_script):
        print(f"Warning: post.sh not found in {mod_path}, skipping manual mod...")
        return True
    env = os.environ.copy()
    script_dir = os.path.dirname(__file__)
    env["KERNEL_WORKSPACE"] = workspace_dir
    env["SCRIPT_DIR"] = os.path.dirname(__file__)
    env["MOD_PATH"] = mod_path
    env["ANDROID_VERSION"] = kconfig.get("android_version")
    env["KERNEL_VERSION"] = kconfig.get("kernel_version")
    env["IMAGE_PATH"] = os.path.join(workspace_dir, "anykernel3/Image")
    env["AK3_DIR"] = os.path.join(workspace_dir, "anykernel3")
    env["DOWNLOAD_FILE"] = os.path.join(script_dir, "kernelbuild.py") + " --download"
    env["APPLY_PATCH"] = os.path.join(script_dir, "kernelbuild.py") + " --applypatch"
    return_code = subprocess.run(["bash", setup_script], cwd=workspace_dir, env=env, check=True)
    if return_code.returncode != 0:
        print(f"Warning: failed to apply manual mod {mod_path}, skipping...")
        return False
    print(f"Manual mod {mod_path} applied successfully.")
    return True
def load_and_apply_mod(workspace_dir, mod_path,config_kernel,is_post_build=False):
    #load config.json
    config_path = os.path.join(mod_path, "config.json")
    if not os.path.isfile(config_path):
        print(f"Warning: config.json not found in {mod_path}, skipping...")
        return False
    with open(config_path, "r") as f:
        config = json.load(f)
    #check if the version is compatible
    supported_versions = config.get("versions", [])
    # load allowfailure from config, default to False
    allow_failure = config.get("allowfailure", True)
    kernel_version = config_kernel.get("version")
    if not check_version_compatibility(supported_versions, kernel_version):
        print(f"Warning: mod {config.get('name')} does not support kernel version {kernel_version}, skipping...")
        return False
    #apply the patch
    if is_post_build:
        return post_mod(workspace_dir, mod_path, config_kernel)
    else:
        return manual_mod(workspace_dir, mod_path, config_kernel, allow_failure=allow_failure)


def apply_mods(workspace_dir, mods_dir, version,is_post_build=False):
    """
    将 mods_dir 中的补丁应用到 workspace_dir 中的内核源代码。
    mods_dir 目录结构如下：
    mods/
        docker_6.12/
            config.json
            patch.diff
            defconfig_append
            ....
    config.json 内容如下：
    {
        "name": "docker_6.12",
        "description": "Docker patch for 6.12",
        "versions": ["6.12",....],
        "dependency": ["other_mod_name", ...],
        "type": "patch"
    }
    """
    # ---------- 依赖解析与拓扑排序 ----------
    mods_info = {}          # mod_name -> { "path": mod_path, "deps": list, "config": dict }
    graph = {}              # 邻接表: mod_name -> list of deps
    indegree = {}           # 入度表

    # 1. 收集所有有效 mod 的信息
    for entry in sorted(os.listdir(mods_dir)):
        mod_path = os.path.join(mods_dir, entry)
        if not os.path.isdir(mod_path):
            print(f"Warning: {mod_path} is not a directory, skipping...")
            continue

        config_path = os.path.join(mod_path, "config.json")
        if not os.path.exists(config_path):
            print(f"Warning: {mod_path} has no config.json, skipping...")
            continue

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error loading config.json from {mod_path}: {e}, skipping...")
            continue

        mod_name = config.get("name")
        if not mod_name:
            print(f"Warning: config.json in {mod_path} missing 'name', skipping...")
            continue

        deps = config.get("dependency", [])
        mods_info[mod_name] = {
            "path": mod_path,
            "deps": deps,
            "config": config
        }
        graph[mod_name] = deps
        indegree[mod_name] = 0   # 先初始化为0，稍后累加

    # 2. 计算入度，同时检查依赖是否存在
    for mod_name, deps in graph.items():
        for dep in deps:
            if dep not in mods_info:
                raise ValueError(f"Mod '{mod_name}' depends on unknown mod '{dep}'")
            indegree[mod_name] += 1

    # 3. 拓扑排序（Kahn算法）
    queue = deque([name for name, deg in indegree.items() if deg == 0])
    sorted_mods = []

    while queue:
        current = queue.popleft()
        sorted_mods.append(current)

        # 找出哪些 mod 依赖于 current
        for mod_name, deps in graph.items():
            if current in deps:
                indegree[mod_name] -= 1
                if indegree[mod_name] == 0:
                    queue.append(mod_name)

    # 检查是否有环
    if len(sorted_mods) != len(mods_info):
        remaining = set(mods_info.keys()) - set(sorted_mods)
        raise ValueError(f"Circular dependency detected among mods: {remaining}")

    # ---------- 按照依赖顺序应用补丁 ----------
    print(f"Applying mods in order: {sorted_mods}")
    total_mods = len(sorted_mods)
    succeeded_mods = 0
    for mod_name in sorted_mods:
        mod_data = mods_info[mod_name]
        print(f"Applying mod {mod_name}...")
        success = load_and_apply_mod(workspace_dir, mod_data["path"], version,is_post_build=is_post_build)
        if success:
            succeeded_mods += 1
    print(f"Finished applying mods. Success: {succeeded_mods}/{total_mods}")
    # 原有的字典序逻辑已移除，完全由依赖顺序替代。

def init_workspace(is_development=False):
    # Create a workspace directory if it doesn't exist
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    workspace_dir = os.path.join(script_dir, "kernel_workspace")
    config=load_config("kernel.json")
    #clean up the workspace directory if it already exists
    if os.path.exists(workspace_dir):
        subprocess.run(["rm", "-rf", workspace_dir], check=True)
    os.makedirs(workspace_dir)
    #create build.env with the content of config
    #empty the build.env if it already exists
    build_env_path = os.path.join(workspace_dir, "build.env")
    #create empty build.env
    #if scriptdir/build.env exists append the content of it to build.env, otherwise create an empty build.env
    with open(build_env_path, "w") as f:
        if os.path.exists(os.path.join(script_dir, "build.env")):
            with open(os.path.join(script_dir, "build.env"), "r") as f2:
                f.write(f2.read())
        pass

    # Download the kernel source code
    source_url = config.get("source")
    if not source_url:
        raise ValueError("Source URL is missing in the config")
    print(f"Downloading kernel source from {source_url}...")
    source_path = download_file(source_url)
    # Unzip the kernel source code to the workspace directory
    # get the only foldername in the zip file
    unzip_file(source_path, workspace_dir, "common")
    print("Kernel source downloaded and extracted.")
    print("Downloading compiler toolchain...")
    for compiler_name, compiler_url in config.get("compiler", {}).items():
        if not compiler_url:
            print(f"Compiler URL for {compiler_name} is missing in the config, skipping...")
            continue
        print(f"Downloading {compiler_name} from {compiler_url}...")
        compiler_path = download_file(compiler_url)
        unzip_file(compiler_path, workspace_dir, compiler_name)
    print("Compiler toolchain downloaded and extracted.")
    # Remove -dirty from setlocalversion
    remove_dirty(workspace_dir)
    # Apply kernel suffix
    #if suffix is provided, use it. Otherwise, use the kernel name as suffix
    suffix = config.get("suffix")
    if suffix:
        apply_kernel_suffix(script_dir, suffix=config.get("suffix"))
    else:
        apply_kernel_suffix(script_dir, suffix=config.get("name"))
    apply_mods(workspace_dir, os.path.join(script_dir, "mods"), config)
    common_dir = os.path.join(workspace_dir, "common")
    #if is_development is True, copy the common directory to common_original for later use
        #append #END_OFFICIAL_MOD_DEFCONFIG to the end of gki_defconfig for later use
    gki_defconfig = os.path.join(common_dir, "arch/arm64/configs/gki_defconfig")
    with open(gki_defconfig, "a") as f:
        f.write("\n#END_OFFICIAL_MOD_DEFCONFIG\n")
    if is_development:
    
        common_original_dir = os.path.join(workspace_dir, "common_original")
        if os.path.exists(common_original_dir):
            subprocess.run(["rm", "-rf", common_original_dir], check=True)
        shutil.copytree(common_dir, common_original_dir)



def start_build(only_config=False):
    # 基础路径设置
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    #清空 #END_OFFICIAL_MOD_DEFCONFIG 之后的内容，恢复到初始状态
    gki_defconfig = os.path.join(script_dir, "kernel_workspace/common/arch/arm64/configs/gki_defconfig")
    with open(gki_defconfig, "r") as f:
        lines = f.readlines()
    with open(gki_defconfig, "w") as f:
        for line in lines:
            f.write(line)
            if line.strip() == "#END_OFFICIAL_MOD_DEFCONFIG":
                f.write("\n")
                break
    #附加defconfig_append的内容到 gki_defconfig 中
    defconfig_append = os.path.join(script_dir, "defconfig_append")
    if os.path.exists(defconfig_append):
        with open(defconfig_append, "r") as f:
            append_lines = f.readlines()
        with open(gki_defconfig, "a") as f:
            f.writelines(append_lines)

    workspace_dir = os.path.join(script_dir, "kernel_workspace")
    common_dir = os.path.join(workspace_dir, "common")
    os.makedirs(common_dir, exist_ok=True)
    # 加载 build.env 环境变量
    build_env_path = os.path.join(workspace_dir, "build.env")
    env = os.environ.copy()
    if os.path.isfile(build_env_path):
        with open(build_env_path, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    env[key] = value
                    #remove surrounding quotes if exist
                    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                        env[key] = value[1:-1]
    else:
        print(f"build.env not found: {build_env_path}")

    # 设置 PATH
    clang_bin_dir = os.path.join(workspace_dir, "clang", "bin")
    rust_bin_dir = os.path.join(workspace_dir, "rust", "bin")
    build_tools_bin_dir = os.path.join(workspace_dir, "build-tools", "bin")
    ccache_bin_dir = "/usr/lib/ccache"

    env["PATH"] = f"{ccache_bin_dir}:{clang_bin_dir}:{build_tools_bin_dir}:{rust_bin_dir}:{env.get('PATH', '')}"

    # 打印编译器版本信息
    def run_version_cmd(cmd, name):
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
            output = result.stdout.strip().split('\n')[0] if result.stdout else "未安装"
            print(f"{name}版本: {output}")
        except Exception:
            print(f"{name}版本: 未安装")

    print("编译器信息:")
    run_version_cmd(f"{clang_bin_dir}/clang --version", "Clang")
    run_version_cmd(f"{clang_bin_dir}/ld.lld --version", "LLD")
    run_version_cmd("rustc -V", "Rustc")
    run_version_cmd("bindgen --version", "Bindgen")
    run_version_cmd("pahole --version", "pahole")

    # 配置 ccache
    ccache_dir = env.get("CCACHE_DIR", os.path.join(script_dir, ".ccache"))
    env["CCACHE_LOGFILE"] = os.path.join(script_dir, "ccache.log")
    env["CCACHE_BASEDIR"] = workspace_dir
    env["CCACHE_DIR"] = ccache_dir

    os.makedirs(ccache_dir, exist_ok=True)
    ccache_conf = os.path.join(ccache_dir, "ccache.conf")
    with open(ccache_conf, "a") as f:
        f.write("sloppiness = file_stat_matches,include_file_ctime,include_file_mtime,pch_defines,file_macro,time_macros\n")

    # 复制 libfakestat.so 和 libfaketimeMT.so 到 common 目录
    lib_dir = os.path.join(script_dir, "lib")
    shutil.copy(os.path.join(lib_dir, "libfakestat.so"), common_dir)
    shutil.copy(os.path.join(lib_dir, "libfaketimeMT.so"), common_dir)
    for so in glob.glob(os.path.join(common_dir, "*.so")):
        os.chmod(so, 0o777)

    # 设置时间劫持相关变量
    env["FAKESTAT"] = "2025-05-25 12:00:00"
    env["FAKETIME"] = "@2025-05-25 13:00:00"
    preload_libs = f"{common_dir}/libfakestat.so {common_dir}/libfaketimeMT.so"
    env["PRELOAD_LIBS"] = preload_libs

    # 创建 cc-wrapper 和 ld-wrapper 脚本
    cc_wrapper = os.path.join(common_dir, "cc-wrapper")
    ld_wrapper = os.path.join(common_dir, "ld-wrapper")
    real_clang = os.path.join(clang_bin_dir, "clang")
    real_ld = "ld.lld"

    with open(cc_wrapper, "w") as f:
        f.write("#!/bin/bash\n")
        f.write(f"export LD_PRELOAD='{preload_libs}'\n")
        f.write(f"export FAKESTAT='{env['FAKESTAT']}'\n")
        f.write(f"export FAKETIME='{env['FAKETIME']}'\n")
        f.write(f"ccache {real_clang} \"$@\"\n")

    with open(ld_wrapper, "w") as f:
        f.write("#!/bin/bash\n")
        f.write(f"export LD_PRELOAD='{preload_libs}'\n")
        f.write(f"export FAKESTAT='{env['FAKESTAT']}'\n")
        f.write(f"export FAKETIME='{env['FAKETIME']}'\n")
        f.write(f"{real_ld} \"$@\"\n")

    os.chmod(cc_wrapper, 0o755)
    os.chmod(ld_wrapper, 0o755)

    # 创建测试脚本并执行简单验证（可选）
    test_wrapper = os.path.join(common_dir, "test-wrapper.sh")
    with open(test_wrapper, "w") as f:
        f.write("#!/bin/bash\n")
        f.write(f"export LD_PRELOAD='{preload_libs}'\n")
        f.write(f"export FAKESTAT='{env['FAKESTAT']}'\n")
        f.write(f"export FAKETIME='{env['FAKETIME']}'\n")
        f.write('echo ">>> Wrapper Check."\n')
        f.write('exec "$@"\n')
    os.chmod(test_wrapper, 0o755)

    print("--- [Wrapper Test] Testing (date) command ---")
    subprocess.run([test_wrapper, "date"], cwd=common_dir, env=env)
    print("--- [Wrapper Test] Testing (stat) command ---")
    subprocess.run([test_wrapper, "stat", "Makefile"], cwd=common_dir, env=env)
    print("--- [Wrapper Test] Testing completed ---")

    # 显示编译前环境时间
    print("--- [Wrapper Test] Environment time before compilation: ---")
    subprocess.run(["bash", "-c", f"LD_PRELOAD='{preload_libs}' date"], cwd=common_dir, env=env)
    print("--- [Wrapper Test] Environment file timestamps before compilation: ---")
    subprocess.run(["bash", "-c", f"LD_PRELOAD='{preload_libs}' stat Makefile"], cwd=common_dir, env=env)

    # 设置内核编译环境变量
    env["RUSTC"] = "rustc"
    env["BINDGEN"] = "bindgen"
    env["CC"] = "clang"
    env["LIBCLANG_PATH"] = os.path.join(workspace_dir, "clang19", "lib")

    kcflags = (
        f"-fdebug-prefix-map={workspace_dir}=. "
        f"-fmacro-prefix-map={workspace_dir}=. "
        f"-ffile-prefix-map={workspace_dir}=. "
        "-no-canonical-prefixes "
        "-O2 "
        "-pipe "
        "-Wno-error "
        "-fno-stack-protector "
        "-D__ANDROID_COMMON_KERNEL__"
    )
    env["KCFLAGS"] = env.get("KCFLAGS", "") + " " + kcflags

    env["HOSTCC"] = "clang"
    env["LD"] = "ld.lld"
    env["HOSTLD"] = "ld.lld"
    env["LLVM"] = "1"
    env["LLVM_IAS"] = "1"
    env["ARCH"] = "arm64"
    env["SUBARCH"] = "arm64"
    env["CROSS_COMPILE"] = "aarch64-linux-gnu-"
    env["AR"] = "llvm-ar"
    env["NM"] = "llvm-nm"
    env["AS"] = "clang"
    env["READELF"] = "llvm-readelf"
    env["OBJCOPY"] = "llvm-objcopy"
    env["OBJDUMP"] = "llvm-objdump"
    env["OBJSIZE"] = "llvm-size"
    env["STRIP"] = "llvm-strip"

    # 忽略 source _setup_env.sh，直接进入 common 目录开始编译

    # 第一步：生成 .config
    make_cmd_defconfig = [
        "make", f"-j{os.cpu_count()}",
        "LLVM=1", "ARCH=arm64", "CROSS_COMPILE=aarch64-linux-gnu-",
        "CC=clang", "LD=ld.lld", "OBJCOPY=llvm-objcopy",
        "O=out", "gki_defconfig"
    ]
    print("Running defconfig:", " ".join(make_cmd_defconfig))
    subprocess.run(make_cmd_defconfig, env=env, check=True, cwd=common_dir)
    if only_config:
        print("Only generating config file, skipping compilation.")
        return
    # 第二步：使用 wrapper 编译 Image
    env["CC"] = os.path.join(common_dir, "cc-wrapper")
    env["LD"] = os.path.join(common_dir, "ld-wrapper")

    make_cmd_image = [
        "make", f"-j{os.cpu_count()}",
        "LLVM=1", "ARCH=arm64", "CROSS_COMPILE=aarch64-linux-gnu-",
        f"CC={env['CC']}", f"LD={env['LD']}", "OBJCOPY=llvm-objcopy",
        "O=out", "Image"
    ]
    print("Building Image:", " ".join(make_cmd_image))
    subprocess.run(make_cmd_image, env=env, check=True,cwd=common_dir)

    print("Kernel compilation completed.")
    print("Processing post-build modifications...")
    config=load_config("kernel.json")
    ak3=config.get("anykernel3")
    ak3zip=download_file(ak3)
    unzip_file(ak3zip, workspace_dir, "anykernel3")
    # copy the built Image to anykernel3
    shutil.copy(os.path.join(common_dir, "out/arch/arm64/boot/Image"), os.path.join(workspace_dir, "anykernel3/Image"))
    apply_mods(workspace_dir, os.path.join(script_dir, "mods"),config, is_post_build=True)
    print("Post-build modifications completed.")
    #zip the anykernel3 folder to anykernel3.zip with zip command, and put it in the workspace directory
    anykernel3_dir = os.path.join(workspace_dir, "anykernel3")
    anykernel3_zip = os.path.join(script_dir, "anykernel3.zip")
    if os.path.exists(anykernel3_zip):
        os.remove(anykernel3_zip)
    subprocess.run(["zip", "-r", anykernel3_zip, "."], cwd=anykernel3_dir, check=True)
    print(f"Packaging completed. Generated zip file path: {anykernel3_zip}")

def gen_patch():
    # generate patch file for the changes in common directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.join(script_dir, "kernel_workspace")
    common_dir = os.path.join(workspace_dir, "common")
    #clean out dir
    out=os.path.join(common_dir, "out")
    subprocess.run(["rm", "-rf", out], check=True)
    common_original_dir = os.path.join(workspace_dir, "common_original")
    if not os.path.exists(common_original_dir):
        print("common_original directory not found, cannot generate patch")
        return
    patch_file = os.path.join(script_dir, "common_changes.patch")
    with open(patch_file, "w") as f:
        subprocess.run(["diff", "-ruN", "common_original", "common"], cwd=workspace_dir, stdout=f)
    with open(patch_file, "r") as f:
        content = f.read()
        new_content = ""
        # diff -ruN line
        for line in content.splitlines():
            if line.startswith("+++ "):
                line = line.replace(" common/", " b/")
                #remove time info in the line
                if "\t" in line:
                    line = line.split("\t")[0]
            elif line.startswith("--- "):
                line = line.replace(" common_original/", " a/")
                if "\t" in line:
                    line = line.split("\t")[0]
            elif line.startswith("diff -ruN "):
                line = line.replace(" common/", " b/")
                line = line.replace(" common_original/", " a/")
                line = line.replace("diff -ruN ", "diff --git ")
            new_content = new_content + line + "\n"
        with open(patch_file, "w") as f:
            f.write(new_content)
    print(f"Patch generated at {patch_file}")

def apply_patch(file_path):
    # apply patch file to common directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.join(script_dir, "kernel_workspace")
    common_dir = os.path.join(workspace_dir, "common")
    patch_file = file_path
    if not os.path.exists(patch_file):
        print("Patch file not found, cannot apply patch")
        return
    try:
        subprocess.run(["patch", "-p1", "-F", "3", "-i", patch_file], cwd=common_dir, check=True)
        print("Patch applied successfully.")
    except subprocess.CalledProcessError:
        print("Failed to apply patch.")

def clean_workspace():
    # Clean the kernel workspace common directory with the original common directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.join(script_dir, "kernel_workspace")
    common_dir = os.path.join(workspace_dir, "common")
    common_original_dir = os.path.join(workspace_dir, "common_original")
    if not os.path.exists(common_original_dir):
        print("common_original directory not found, cannot clean workspace")
        return
    # remove common directory and copy common_original to common
    subprocess.run(["rm", "-rf", common_dir], check=True)
    shutil.copytree(common_original_dir, common_dir)
    print("Workspace cleaned, common directory restored to original state.")
def dump_symbol(kernel_structure, output_file):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.join(script_dir, "kernel_workspace")
    common_dir = os.path.join(workspace_dir, "common")
    kimage = os.path.join(common_dir, "out/vmlinux")
    if not os.path.exists(kimage):
        print("Kernel image not found, cannot dump symbol")
        return
    try:
        result = subprocess.run(["pahole", "-C", kernel_structure, kimage], capture_output=True, text=True, check=True)
        with open(output_file, "w") as f:
            f.write(result.stdout)
        print(f"Symbol table dumped to {output_file}")
    except subprocess.CalledProcessError:
        print("Failed to dump symbol table.")
if __name__ == "__main__":
    # 参数解析
    parser = argparse.ArgumentParser(description="Kernel Build Script")
    parser.add_argument("--build", action="store_true", help="Start the kernel build process")
    parser.add_argument("--genpatch", action="store_true", help="Generate patch file for changes in common directory")
    parser.add_argument("--applypatch", nargs=1, metavar="PATCH_FILE", help="Apply patch file to common directory")
    parser.add_argument("--init", action="store_true", help="Initialize the kernel workspace")
    parser.add_argument("--dev", action="store_true", help="Initialize workspace in development mode (keep original common directory)")
    parser.add_argument("--clean", action="store_true", help="Clean the kernel workspace common directory with the original common directory")
    parser.add_argument("--dumpsymbol", nargs=2, metavar=("KERNEL_IMAGE", "OUTPUT_FILE"), help="Dump the symbol table of the kernel structure using pahole and save it to a file")
    #helper for downloading files, not used in the main flow
    parser.add_argument("--download", nargs=2, metavar=("URL", "OUTPUT_PATH"), help="Download a file from URL to OUTPUT_PATH using the download_file function")
    parser.add_argument("--dumpconfig", nargs=1, metavar="OUTPUT_FILE", help="Dump the current kernel configuration to a file")
    parser.add_argument("--auto", action="store_true", help="Automatically initialize and build the kernel")
    args = parser.parse_args()
    if args.init:
        if args.dev:
            init_workspace(is_development=True)
        else:
            init_workspace()
    if args.clean:
        clean_workspace()
    if args.build:
        start_build()
    if args.genpatch:
        gen_patch()
    if args.applypatch:
        apply_patch(args.applypatch[0])
    if args.auto:
        init_workspace()
        start_build()
    if args.download:
        url, output_path = args.download
        downloaded_file = download_file(url)
        shutil.copy(downloaded_file, output_path)
        print(f"File downloaded from {url} to {output_path}")
    if args.dumpsymbol:
        kernel_structure, output_file = args.dumpsymbol
        dump_symbol(kernel_structure, output_file)
    if args.dumpconfig:
        start_build(only_config=True)
        output_file = args.dumpconfig[0]
        script_dir = os.path.dirname(os.path.abspath(__file__))
        workspace_dir = os.path.join(script_dir, "kernel_workspace")
        common_dir = os.path.join(workspace_dir, "common")
        config_path = os.path.join(common_dir, "out/.config")
        if not os.path.exists(config_path):
            print("Kernel config not found, cannot dump config")
            exit(1)
        shutil.copy(config_path, output_file)
        print(f"Kernel config dumped to {output_file}")
