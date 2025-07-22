#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import traceback
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    try:
        print("正在初始化应用程序...")
        app = QApplication(sys.argv)
        print("正在创建主窗口...")
        window = MainWindow()
        print("正在显示主窗口...")
        window.show()
        print("应用程序启动完成，进入事件循环")
        sys.exit(app.exec())
    except Exception as e:
        print(f"程序启动时发生错误：{str(e)}")
        print("错误详情：")
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()
