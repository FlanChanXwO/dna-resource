# -*- coding: utf-8 -*-
"""让 pytest 能直接导入 scripts/ 下的维护脚本模块。

测试位于 scripts/tests/，被检文件位于 scripts/，故加入上一级目录。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
