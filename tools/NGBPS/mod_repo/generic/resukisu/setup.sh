echo "正在配置ReSukiSU..."
source ./build.env
curl -LSs "https://raw.githubusercontent.com/ReSukiSU/ReSukiSU/refs/heads/main/kernel/setup.sh" | bash -s main
echo KSU=resukisu >> build.env
echo "ReSukiSU配置完成！"
echo "CONFIG_KSU=y" >> ./common/arch/arm64/configs/gki_defconfig
if [[ "$KPM" == "builtin" ]]; then
  echo "CONFIG_KPM=y" >> ./common/arch/arm64/configs/gki_defconfig
fi