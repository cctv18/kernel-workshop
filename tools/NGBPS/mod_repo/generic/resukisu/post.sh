source ./build.env
if [[ "$KPM" == 'builtin' ]]; then
python $SCRIPT_DIR/kernelbuild.py --download https://github.com/SukiSU-Ultra/SukiSU_KernelPatch_patch/releases/latest/download/patch_linux $MOD_PATH/patch_linux
chmod +x $MOD_PATH/patch_linux
cp $IMAGE_PATH $MOD_PATH/Image
cd $MOD_PATH
./patch_linux
mv oImage $IMAGE_PATH
rm -f $MOD_PATH/patch_linux
rm -f $MOD_PATH/Image
fi