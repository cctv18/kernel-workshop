echo "正在配置ReSukiSU..."
source ./build.env

if [[ "$BBR_DEFAULT" == "true" ]]; then
  echo "正在将BBR设为默认拥塞控制算法..."
  echo "CONFIG_DEFAULT_TCP_CONG=bbr" >> ./common/arch/arm64/configs/gki_defconfig
else
  echo "CONFIG_DEFAULT_TCP_CONG=cubic" >> ./common/arch/arm64/configs/gki_defconfig
fi
