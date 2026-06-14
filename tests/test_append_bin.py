import os
import tempfile
import numpy as np
from kline_fetcher.converter import KLineToQlib


class TestAppendBin:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, "test.day.bin")

    def teardown_method(self):
        if os.path.exists(self.bin_path):
            os.remove(self.bin_path)
        os.rmdir(self.tmpdir)

    def _read_bin(self):
        raw = np.fromfile(self.bin_path, dtype="<f")
        return int(raw[0]), raw[1:]

    def test_new_file(self):
        data = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        KLineToQlib._append_bin(self.bin_path, data, 10)
        start, values = self._read_bin()
        assert start == 10
        np.testing.assert_array_almost_equal(values, data)

    def test_append_adjacent(self):
        existing = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        full = np.hstack([np.array([10], dtype="<f"), existing.astype("<f")])
        full.tofile(str(self.bin_path))

        new = np.array([4.0, 5.0], dtype=np.float32)
        KLineToQlib._append_bin(self.bin_path, new, 13)

        start, values = self._read_bin()
        assert start == 10, f"start_idx should be 10 (existing_start), got {start}"
        assert len(values) == 5
        np.testing.assert_array_almost_equal(values, [1.0, 2.0, 3.0, 4.0, 5.0])

    def test_append_with_gap(self):
        existing = np.array([1.0, 2.0], dtype=np.float32)
        full = np.hstack([np.array([10], dtype="<f"), existing.astype("<f")])
        full.tofile(str(self.bin_path))

        new = np.array([5.0, 6.0], dtype=np.float32)
        KLineToQlib._append_bin(self.bin_path, new, 15)

        start, values = self._read_bin()
        assert start == 10, f"start_idx should be 10 (existing_start), got {start}"
        assert len(values) == 7
        np.testing.assert_array_almost_equal(values[:2], [1.0, 2.0])
        assert np.isnan(values[2])
        assert np.isnan(values[3])
        assert np.isnan(values[4])
        np.testing.assert_array_almost_equal(values[5:], [5.0, 6.0])

    def test_append_overlap(self):
        existing = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
        full = np.hstack([np.array([10], dtype="<f"), existing.astype("<f")])
        full.tofile(str(self.bin_path))

        new = np.array([30.0, 40.0, 50.0], dtype=np.float32)
        KLineToQlib._append_bin(self.bin_path, new, 12)

        start, values = self._read_bin()
        assert start == 10, f"start_idx should be 10 (existing_start), got {start}"
        assert len(values) == 5
        np.testing.assert_array_almost_equal(values, [1.0, 2.0, 30.0, 40.0, 50.0])

    def test_no_change_when_subset(self):
        existing = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
        full = np.hstack([np.array([10], dtype="<f"), existing.astype("<f")])
        full.tofile(str(self.bin_path))

        new = np.array([99.0, 99.0], dtype=np.float32)
        KLineToQlib._append_bin(self.bin_path, new, 11)

        start, values = self._read_bin()
        assert start == 10
        np.testing.assert_array_almost_equal(values, existing)

    def test_prepend_adjacent(self):
        existing = np.array([4.0, 5.0], dtype=np.float32)
        full = np.hstack([np.array([12], dtype="<f"), existing.astype("<f")])
        full.tofile(str(self.bin_path))

        new = np.array([1.0, 2.0], dtype=np.float32)
        KLineToQlib._append_bin(self.bin_path, new, 10)

        start, values = self._read_bin()
        assert start == 10
        assert len(values) == 4
        np.testing.assert_array_almost_equal(values, [1.0, 2.0, 4.0, 5.0])

    def test_prepend_with_gap(self):
        existing = np.array([5.0, 6.0], dtype=np.float32)
        full = np.hstack([np.array([14], dtype="<f"), existing.astype("<f")])
        full.tofile(str(self.bin_path))

        new = np.array([1.0, 2.0], dtype=np.float32)
        KLineToQlib._append_bin(self.bin_path, new, 10)

        start, values = self._read_bin()
        assert start == 10
        assert len(values) == 6
        np.testing.assert_array_almost_equal(values[:2], [1.0, 2.0])
        assert np.all(np.isnan(values[2:4]))
        np.testing.assert_array_almost_equal(values[4:], [5.0, 6.0])

    def test_overlap_nan_does_not_overwrite_existing(self):
        """#6/#7: 重叠区新数据含 NaN 时，不应覆盖旧的有效值。"""
        # 旧数据：idx 10..14 = [1,2,3,4,5]
        existing = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
        full = np.hstack([np.array([10], dtype="<f"), existing.astype("<f")])
        full.tofile(str(self.bin_path))

        # 新数据：idx 12..15 = [30, NaN, 50, 60]，与旧数据重叠 idx 12,13,14
        # 旧 [3,4,5] vs 新 [30,NaN,50]：30 覆盖 3，NaN 不覆盖 4，50 覆盖 5
        new = np.array([30.0, np.nan, 50.0, 60.0], dtype=np.float32)
        KLineToQlib._append_bin(self.bin_path, new, 12)

        start, values = self._read_bin()
        assert start == 10
        assert len(values) == 6
        # idx10=1, idx11=2, idx12=30(新), idx13=4(NaN没覆盖,保留旧), idx14=50(新), idx15=60(新)
        np.testing.assert_array_almost_equal(values, [1.0, 2.0, 30.0, 4.0, 50.0, 60.0])

    def test_prepend_overlap_nan_does_not_overwrite_existing(self):
        """#6/#7 分支2：新数据在旧数据之前且有重叠，重叠区 NaN 不覆盖旧有效值。"""
        # 旧数据：idx 13..15 = [3,4,5]
        existing = np.array([3.0, 4.0, 5.0], dtype=np.float32)
        full = np.hstack([np.array([13], dtype="<f"), existing.astype("<f")])
        full.tofile(str(self.bin_path))

        # 新数据：idx 10..14 = [1,2,NaN,40,NaN]，与旧数据重叠 idx 13,14
        # 旧 [3,4] vs 新 [40,NaN]：40 覆盖 3，NaN 不覆盖 4
        new = np.array([1.0, 2.0, np.nan, 40.0, np.nan], dtype=np.float32)
        KLineToQlib._append_bin(self.bin_path, new, 10)

        start, values = self._read_bin()
        assert start == 10
        assert len(values) == 6
        # idx10=1, idx11=2, idx12=NaN(新,无旧), idx13=40(新覆盖旧3), idx14=4(NaN没覆盖,保留旧), idx15=5(旧)
        np.testing.assert_array_almost_equal(values[:2], [1.0, 2.0])
        assert np.isnan(values[2])
        assert values[3] == 40.0
        assert values[4] == 4.0  # NaN 没覆盖
        assert values[5] == 5.0
