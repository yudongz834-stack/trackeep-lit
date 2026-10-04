# atomic_retry_test.py — _replace_retry 退避重试测试（审核 L-3 整改：杀毒抢锁场景无回归覆盖）
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lit.overrides import _replace_retry as retry_overrides
from lit.strategy import _replace_retry as retry_strategy


class AtomicRetryTests(unittest.TestCase):
    def test_transient_lock_survived_by_both_impls(self):
        for mod_name, fn in (('lit.overrides', retry_overrides), ('lit.strategy', retry_strategy)):
            calls = {'n': 0}
            real = os.replace

            def flaky(src, dst):
                calls['n'] += 1
                if calls['n'] == 1:
                    raise PermissionError(5, '拒绝访问。')
                real(src, dst)

            with tempfile.TemporaryDirectory() as d:
                a, b = os.path.join(d, 'a'), os.path.join(d, 'b')
                open(a, 'w', encoding='utf-8').write('x')
                with patch(mod_name + '.os.replace', flaky):
                    fn(a, b)  # 第一次撞锁→退避→第二次成功，不抛
                self.assertEqual(open(b, encoding='utf-8').read(), 'x', mod_name)

    def test_persistent_lock_raises_after_exhaustion(self):
        def always(_src, _dst):
            raise PermissionError(5, '拒绝访问。')

        with tempfile.TemporaryDirectory() as d:
            a = os.path.join(d, 'a')
            open(a, 'w', encoding='utf-8').write('x')
            with patch('lit.overrides.os.replace', always):
                with self.assertRaises(PermissionError):
                    retry_overrides(a, os.path.join(d, 'b'))


if __name__ == '__main__':
    unittest.main()
