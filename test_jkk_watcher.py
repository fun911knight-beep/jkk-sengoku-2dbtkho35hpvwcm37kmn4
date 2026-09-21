import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("jkk_watcher", ROOT / "jkk_watcher.py")
WATCHER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(WATCHER)


class ParserTests(unittest.TestCase):
    def test_summary_row(self):
        page = '''
        <tr class="ListTXT1">
          <td><img src="x"></td><td>コーシャハイム千石</td><td>文京区</td>
          <td>一般</td><td>一般賃貸住宅（期限付）</td><td>２ＬＤＫ</td>
          <td>60.0</td><td>180,000</td><td>5,200</td><td>1</td>
          <td><a onclick="javascript:senPage('','L9999','1234567','0000'); return false">詳細</a></td>
        </tr>'''
        rows = WATCHER.extract_summary_rows(page)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["application_code"], "L9999")
        self.assertEqual(rows[0]["layout"], "2LDK")
        self.assertEqual(rows[0]["count"], 1)

    def test_detail_room(self):
        page = '''
        <tr align="center">
          <td><img src="x"></td><td>1-203</td><td>1～</td><td>L2</td>
          <td>２ＬＤＫ</td><td>南</td><td>180,000</td><td>360,000</td>
          <td>5,200</td><td>文京区千石</td><td>即入居可</td><td>内見</td><td>申込</td>
        </tr>'''
        summary = {"application_code": "L9999"}
        rooms = WATCHER.extract_detail_rooms(page, summary)
        self.assertEqual(rooms[0]["key"], "L9999:1-203")
        self.assertEqual(rooms[0]["layout"], "2LDK")
        self.assertEqual(rooms[0]["rent"], "180,000")

    def test_notification_text(self):
        text = WATCHER.format_notification(
            [{"room": "1-203", "layout": "2LDK", "rent": "180,000", "fee": "5,200"}]
        )
        self.assertIn("1-203号室", text)
        self.assertIn("家賃180,000円", text)


if __name__ == "__main__":
    unittest.main()
