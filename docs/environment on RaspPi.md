# System prepare
* sudo raspi-config
* htop



sudo apt update
sudo apt upgrade -y

sudo apt install python3-opencv -y
// 验证 python 是否可以使用 opencv
python
>>> import cv2
>>>


sudo apt install git -y
git clone https://github.com/voicevon/asparagus_bot.git


cd asparagus_bot
sudo apt install python3-full -y
sudo apt install python3-pip -y
sudo apt install python3-venv -y
python3 -m venv asp8
source asp8/bin/activate
pip install -r requirements.txt


// 查看已安装的包
pip list






