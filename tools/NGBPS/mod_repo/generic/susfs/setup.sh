source ./build.env
if [[ "$KSU" != "none" ]]; then
  echo "正在添加susfs补丁..."
  git clone --depth=1 https://github.com/cctv18/susfs4oki.git susfs4ksu -b oki-${ANDROID_VERSION}-${KERNEL_VERSION}
  cp ./susfs4ksu/kernel_patches/50_add_susfs_in_gki-${ANDROID_VERSION}-${KERNEL_VERSION}.patch ./common/
  cp ./susfs4ksu/kernel_patches/fs/* ./common/fs/
  cp ./susfs4ksu/kernel_patches/include/linux/* ./common/include/linux/
  cd ./common
  patch -p1 < 50_add_susfs_in_gki-${ANDROID_VERSION}-${KERNEL_VERSION}.patch || true
  cd ..
else
  echo "已选择无内置KernelSU模式，跳过susfs配置..."
fi
if [[ "$KSU" == "ksu" ]]; then
  echo "正在为原版 KernelSU (tiann/KernelSU)添加补丁..."
  cp ./susfs4ksu/kernel_patches/KernelSU/10_enable_susfs_for_ksu.patch ./KernelSU/
  cd ./KernelSU
  patch -p1 < 10_enable_susfs_for_ksu.patch || true
  cd ..
fi