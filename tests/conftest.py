# -*- coding: utf-8 -*-
"""让测试能直接导入 scripts/ 下的模块。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
