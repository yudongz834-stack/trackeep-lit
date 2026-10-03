"""原生窗口识别的合成回归，不读取或操作真实桌面。"""
import sys
import ctypes
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lit import native_ui as ui


def control(kind, identifier):
    value = Mock()
    value.kind = kind
    value.element_info.automation_id = identifier
    value.is_visible.return_value = True
    return value


def window(handle, controls=(), pid=10):
    value = Mock()
    value.handle = handle
    value.process_id.return_value = pid
    value.element_info.class_name = 'MozillaWindowClass'
    value.descendants.side_effect = lambda control_type: [c for c in controls if c.kind == control_type]
    return value


class NativeWindows(unittest.TestCase):
    def setUp(self):
        ownership = patch.object(ui, 'dialog_belongs', side_effect=lambda main, c: c.process_id() == main.process_id())
        ownership.start()
        self.addCleanup(ownership.stop)

    def test_activation_calls_win32_then_confirms_foreground(self):
        main, user32 = Mock(), Mock()
        main.handle = 123
        with patch.object(ctypes, 'windll', SimpleNamespace(user32=user32), create=True), patch.object(ui, 'foreground') as check:
            ui.activate_main(main)
        main.set_focus.assert_called_once()
        user32.SetForegroundWindow.assert_called_once_with(123)
        check.assert_called_once_with(main, 'after_activate')

    def test_activation_cannot_bypass_foreground_denial(self):
        main, user32 = Mock(), Mock()
        with patch.object(ctypes, 'windll', SimpleNamespace(user32=user32), create=True), patch.object(ui, 'foreground', side_effect=RuntimeError('拒绝前台')), patch.object(ui.time, 'monotonic', side_effect=[0, 2]):
            with self.assertRaisesRegex(RuntimeError, '拒绝前台'):
                ui.activate_main(main)

    def test_focus_is_verified_before_mouse_input(self):
        main, row = Mock(), Mock()
        with patch.object(ui, 'activate_main') as activate, patch.object(ui, 'foreground') as check, patch.object(ui, 'selected', return_value=row):
            self.assertIs(ui.focus_target(main, 'title', 'doi', '123'), row)
        activate.assert_called_once_with(main)
        self.assertEqual(check.call_count, 2)

    def test_lost_foreground_stops_before_selection(self):
        main = Mock()
        with patch.object(ui, 'activate_main'), patch.object(ui, 'foreground', side_effect=RuntimeError('前台丢失')), patch.object(ui, 'selected') as selected:
            with self.assertRaisesRegex(RuntimeError, '前台'):
                ui.focus_target(main, 'title', 'doi', '123')
        selected.assert_not_called()

    def test_menu_waits_without_repeating_mouse_input(self):
        main, menu = Mock(), Mock()
        menu.is_visible.return_value = menu.is_enabled.return_value = True
        menu.window_text.return_value = '查找全文'
        main.descendants.side_effect = [[], [menu]]
        with patch.object(ui, 'foreground'), patch.object(ui, 'selected'), patch.object(ui.time, 'sleep'):
            self.assertIs(ui.find_menu(main, 'title', 'doi', '123'), menu)
        main.click_input.assert_not_called()

    def test_missing_menu_has_bounded_diagnostic(self):
        main = Mock()
        main.descendants.return_value = []
        with patch.object(ui, 'foreground'), patch.object(ui, 'selected'):
            with self.assertRaisesRegex(RuntimeError, '匹配数=0'):
                ui.find_menu(main, 'title', 'doi', '123', timeout=0)

    def test_main_ignores_reader_and_file_dialog(self):
        main = window(1, [control('Tree', 'item-tree-main-default')])
        reader = window(2)
        dialog = window(3, [control('Edit', '1148'), control('Button', '1')])
        desktop = Mock()
        desktop.windows.return_value = [reader, dialog, main]
        process = Mock()
        process.exe.return_value = 'E:/Software/Zotero/zotero.exe'
        with patch.dict(sys.modules, {'pywinauto': SimpleNamespace(Desktop=lambda **kwargs: desktop),
                                     'psutil': SimpleNamespace(Process=lambda pid: process, Error=RuntimeError)}):
            self.assertIs(ui.window(), main)
            desktop.windows.return_value.append(window(4, [control('Tree', 'item-tree-main-default')]))
            with self.assertRaisesRegex(RuntimeError, '唯一'):
                ui.window()

    def test_file_dialog_ignores_other_windows_and_processes(self):
        main = window(1)
        edit, button = control('Edit', '1148'), control('Button', '1')
        target = window(3, [edit, button])
        foreign = window(4, [edit, button], pid=20)
        self.assertEqual(ui.file_dialog(main, [main, window(2), target, foreign]), (target, edit, button))

    def test_two_file_dialogs_stop(self):
        controls = [control('Edit', '1148'), control('Button', '1')]
        with self.assertRaisesRegex(RuntimeError, '唯一'):
            ui.file_dialog(window(1), [window(2, controls), window(3, controls)])

    def test_filename_edit_nested_in_combo(self):
        edit, button = control('Edit', '1001'), control('Button', '1')
        combo = control('ComboBox', '1148')
        combo.descendants.return_value = [edit]
        target = window(2, [combo, edit, button])
        self.assertEqual(ui.file_dialog(window(1), [target]), (target, edit, button))

    def test_modal_is_nested_in_main_and_other_process(self):
        edit, button = control('Edit', '1148'), control('Button', '1')
        target = window(3, [edit, button], pid=11)
        main = window(1)
        main.descendants.return_value = [target]
        main.descendants.side_effect = None
        with patch.object(ui, 'dialog_belongs', return_value=True):
            self.assertEqual(ui.file_dialog(main, [main]), (target, edit, button))

    def test_duplicate_modal_listing_does_not_make_two_targets(self):
        edit, button = control('Edit', '1148'), control('Button', '1')
        target = window(3, [edit, button])
        main = window(1)
        main.descendants.side_effect = None
        main.descendants.return_value = [target]
        self.assertEqual(ui.file_dialog(main, [main, target]), (target, edit, button))

    def test_two_filename_edits_in_combo_stop(self):
        combo = control('ComboBox', '1148')
        combo.descendants.return_value = [control('Edit', '1001'), control('Edit', '1002')]
        with self.assertRaisesRegex(RuntimeError, '唯一'):
            ui.file_dialog(window(1), [window(2, [combo, control('Button', '1')])])

    def test_hidden_file_control_is_not_target(self):
        edit = control('Edit', '1148')
        edit.is_visible.return_value = False
        with self.assertRaisesRegex(RuntimeError, '唯一'):
            ui.file_dialog(window(1), [window(2, [edit, control('Button', '1')])])


if __name__ == '__main__':
    unittest.main()
