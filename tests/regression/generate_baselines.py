#!/usr/bin/env python3
"""Generate or refresh locked baselines for the regression suite.

Called directly (python3 tests/regression/generate_baselines.py) or via
'make update-baselines'. Uses REGRESSION_CAROUSEL so all 9 slide types
are covered, including the explainer slide absent from TEST_CAROUSEL.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'watcher'))
sys.path.insert(0, os.path.dirname(__file__))

from renderer import render_carousel
from test_renderer_regression import REGRESSION_CAROUSEL

BASELINE_DIR = os.path.join(os.path.dirname(__file__), 'baselines')

if __name__ == '__main__':
    os.makedirs(BASELINE_DIR, exist_ok=True)
    paths = render_carousel(REGRESSION_CAROUSEL, output_dir=BASELINE_DIR, prefix='baseline')
    print(f'Baselines updated — {len(paths)} files written to {BASELINE_DIR}')
