"""Static contracts for the shared Jarvis UI shell.

These checks intentionally avoid importing Qt.  Runtime geometry and worker
behavior are covered by the bounded desktop smoke script used in handoff.
"""

from pathlib import Path
import os
import sys
import unittest


SOURCE = (Path(__file__).parents[1] / "jarvis_ui.py").read_text(encoding="utf-8")
CHAT_HTML = (Path(__file__).parents[1] / "assets" / "CHAT" / "chat.html").read_text(encoding="utf-8")


class UIShellContractTests(unittest.TestCase):
    def test_settings_has_one_scroll_host(self):
        self.assertIn('settings_scroll.setWidgetResizable(True)', SOURCE)
        self.assertIn('settings_scroll.setHorizontalScrollBarPolicy', SOURCE)
        self.assertIn('settings_body.addWidget(settings_scroll, 1)', SOURCE)

    def test_top_level_pages_cannot_raise_shell_minimum(self):
        self.assertIn('container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)', SOURCE)
        self.assertIn('self.pages.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)', SOURCE)

    def test_fullscreen_restore_uses_single_normal_geometry(self):
        self.assertIn('self._normal_geometry = QRect(self.geometry())', SOURCE)
        transition = SOURCE.split('def toggle_fullscreen_window(self):', 1)[1].split('def changeEvent(self, event):', 1)[0]
        self.assertNotIn('setFixedSize(', transition)
        self.assertNotIn('QTimer.singleShot(', transition)

    def test_settings_scroll_fits_the_visible_page(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        sys.path.insert(0, str(Path(__file__).parents[1]))
        from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QVBoxLayout, QWidget
        from jarvis_ui import CurrentPageStack

        app = QApplication.instance() or QApplication([])
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        stack = CurrentPageStack()
        short_page = QWidget()
        short_layout = QVBoxLayout(short_page)
        wrapped = QLabel('A short settings description that wraps at narrow widths. ' * 3)
        wrapped.setWordWrap(True)
        short_layout.addWidget(wrapped)
        stack.addWidget(short_page)
        tall_page = QWidget()
        tall_layout = QVBoxLayout(tall_page)
        tall_content = QLabel('Long provider settings')
        tall_content.setFixedHeight(690)
        tall_layout.addWidget(tall_content)
        stack.addWidget(tall_page)
        scroll.setWidget(stack)
        scroll.resize(500, 300)
        scroll.show()
        app.processEvents()
        self.assertEqual(scroll.verticalScrollBar().maximum(), 0)
        stack.setCurrentIndex(1)
        app.processEvents()
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
        stack.setCurrentIndex(0)
        app.processEvents()
        self.assertEqual(scroll.verticalScrollBar().maximum(), 0)
        scroll.close()

    def test_provider_worker_lifetime_and_ui_callback_are_explicit(self):
        self.assertIn('def start_network_operation(', SOURCE)
        self.assertIn('target=worker.run', SOURCE)
        self.assertIn('Qt.ConnectionType.QueuedConnection', SOURCE)
        self.assertIn('provider.ui.loaded', SOURCE)
        self.assertIn('panel.setMaximumWidth(960)', SOURCE)

    def test_finished_network_jobs_cannot_block_window_close(self):
        self.assertIn('QThread-owned Python QObject teardown repeatedly crashed in shiboken6', SOURCE)
        self.assertIn('jobs[:] = [job for job in jobs if len(job) < 4 or job[3] is not token]', SOURCE)
        self.assertIn('completion_callback=self._network_operation_finished', SOURCE)
        self.assertIn('def _prune_network_jobs(self):', SOURCE)
        finished_block = SOURCE.split('def _network_operation_finished', 1)[1].split(
            'def _refresh_active_chat_visuals', 1
        )[0]
        self.assertNotIn('JarvisUI._prune_network_jobs(self)', finished_block.split('else:', 1)[1])
        self.assertIn('job[3] is not job_token', finished_block)
        close_block = SOURCE.rsplit('    def closeEvent(self, event):', 1)[1].split(
            '    def mousePressEvent(self, event):', 1
        )[0]
        self.assertIn('if self._network_jobs:', close_block)
        self.assertNotIn('self._prune_network_jobs()', close_block)

    def test_theme_is_owned_by_the_root_stylesheet(self):
        self.assertIn('stylesheet = ("""', SOURCE)
        self.assertIn('__JARVIS_CONTAINER_BACKGROUND__', SOURCE)
        self.assertNotIn('self.main_container.setStyleSheet', SOURCE)

    def test_shared_inputs_use_glass_theme(self):
        self.assertIn('QSpinBox, QPlainTextEdit, QTextEdit', SOURCE)
        self.assertIn('background:rgba(4,10,18,180)', SOURCE)
        self.assertNotIn('background:white;', SOURCE)

    def test_provider_switch_has_readable_state_labels(self):
        self.assertIn('self.setFixedSize(78, 28)', SOURCE)
        self.assertIn('QColor("#17303a") if self.isChecked()', SOURCE)
        self.assertIn('text_rect = QRectF(7 if self.isChecked() else 43, 3, 33, 22)', SOURCE)

    def test_provider_save_is_explicit_and_dialog_payload_is_isolated(self):
        self.assertIn('saved.clicked.connect(save_state)', SOURCE)
        self.assertIn('saved.setText("SAVE")', SOURCE)
        payload_block = SOURCE.split('    def payload(self):', 1)[1].split('    def fetch_models(self):', 1)[0]
        self.assertIn('fields = {', payload_block)
        self.assertIn('value = self.model.currentText().strip()', payload_block)
        self.assertNotIn('self.model.text().strip()', payload_block)
        self.assertIn('callback=self._apply_saved_provider', SOURCE)

    def test_provider_model_is_read_only_backend_catalogue_selector(self):
        self.assertIn('self.model = QComboBox()', SOURCE)
        self.assertIn('self.model.setEditable(False)', SOURCE)
        self.assertIn('def _set_model_choices(self, models, selected_model=""):', SOURCE)
        self.assertIn('self.model.addItems(options)', SOURCE)
        self.assertIn('QTimer.singleShot(0, self.fetch_models)', SOURCE)

    def test_chat_send_uses_the_shared_network_lifecycle(self):
        self.assertIn('elif self.operation == "chat-send":', SOURCE)
        self.assertIn('"chat-send",\n            self._chat_request_finished,', SOURCE)
        self.assertNotIn('class ChatRequestWorker(QObject):', SOURCE)

    def test_sidebar_marks_background_replies_and_promotes_written_chat(self):
        self.assertIn('self._unread_chat_ids = set()', SOURCE)
        self.assertIn('self._recent_chat_activity = {}', SOURCE)
        self.assertIn('self._unread_chat_ids.add(response_chat_id)', SOURCE)
        self.assertIn('self._unread_chat_ids.discard(chat_id)', SOURCE)
        self.assertIn('self._recent_chat_activity[str(self._chat_request_chat_id)]', SOURCE)
        self.assertIn('self.unread_dot.setToolTip("Есть новый ответ")', SOURCE)

    def test_runtime_delta_polling_avoids_per_request_qthread_teardown(self):
        block = SOURCE.split('    def _start_runtime_delta_worker(self):', 1)[1].split(
            '    def _stop_runtime_delta_worker(self):', 1
        )[0]
        self.assertIn('threading.Thread(', block)
        self.assertIn('Qt.ConnectionType.QueuedConnection', block)
        self.assertIn('self._runtime_delta_generation == generation', block)
        self.assertNotIn('QThread(', block)

    def test_general_settings_use_separate_glass_tint_and_stable_quick_links(self):
        self.assertIn('self._set_glass_tint(value)', SOURCE)
        self.assertIn('self.visual_settings["glass_tint"]', SOURCE)
        self.assertIn('self.open_settings_section(row)', SOURCE)
        self.assertIn('container_background = "rgba(15,15,20,245)"', SOURCE)
        self.assertIn('self.glass_hint.setText("Включено" if', SOURCE)

    def test_authenticated_account_email_populates_both_profile_views(self):
        self.assertIn('self._sync_authenticated_email_to_profile()', SOURCE)
        self.assertIn('coordinator.context().account.email', SOURCE)
        self.assertIn('self.ui_settings.setValue("profile_email", email)', SOURCE)

    def test_device_capabilities_use_actionable_two_column_cards(self):
        self.assertIn('capability_grid.addWidget(card, index // 2, index % 2)', SOURCE)
        self.assertIn('class CapabilityCard(QPushButton):', SOURCE)
        self.assertIn('self.setMinimumHeight(138)', SOURCE)
        card_init = SOURCE.split('class CapabilityCard(QPushButton):', 1)[1].split(
            'def set_capability_state', 1
        )[0]
        self.assertLess(
            card_init.index('text_layout.addWidget(self.status_label)'),
            card_init.index('text_layout.addStretch(1)'),
        )
        self.assertIn('card = CapabilityCard(capability_name, capability_assets_dir / asset_name)', SOURCE)
        self.assertIn('card.set_capability_state(', SOURCE)
        self.assertIn('def activate_capability(capability_id):', SOURCE)
        self.assertIn('QPropertyAnimation(self.image_label, b"geometry", self)', SOURCE)
        self.assertIn('capability_assets_dir = Path(BASE_DIR) / "assets" / "capabilities"', SOURCE)
        self.assertIn('refresh_devices.setObjectName("providerAction")', SOURCE)
        self.assertIn('snapshot_button.setObjectName("providerAction")', SOURCE)
        self.assertIn('devices_actions.setSpacing(12)', SOURCE)
        self.assertIn('refresh_devices.setFixedSize(220, 38)', SOURCE)
        self.assertIn('snapshot_button.setFixedSize(220, 38)', SOURCE)
        self.assertIn('devices_actions.addStretch(1)', SOURCE)

    def test_chat_readiness_and_sidebar_outline_are_stable(self):
        self.assertIn('"#00aaff", "Модель готова к работе"', SOURCE)
        self.assertIn('model_status_row.setSpacing(15)', SOURCE)
        self.assertIn('model_status_row.addWidget(self.chat_status_dot', SOURCE)
        self.assertIn('self.chat_identity.setFixedWidth(430)', SOURCE)
        self.assertIn('header_layout.addWidget(self.chat_identity)', SOURCE)
        self.assertIn('Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter', SOURCE)
        self.assertIn('title_row.addStretch(1)', SOURCE)
        self.assertIn('self.rect().adjusted(1, 1, -2, -2)', SOURCE)
        self.assertIn('setViewportMargins(2, 0, 2, 0)', SOURCE)

    def test_hud_global_fallback_cannot_steal_chat_or_model_clicks(self):
        self.assertIn('def _hud_fallback_enabled(self) -> bool:', SOURCE)
        self.assertIn('pages.currentIndex() == 0', SOURCE)
        press = SOURCE.split('def handle_hud_global_press', 1)[1].split(
            'def raise_hud_controls', 1
        )[0]
        release = SOURCE.split('def handle_hud_global_release', 1)[1].split(
            'def _hud_fallback_enabled', 1
        )[0]
        self.assertIn('if not self._hud_fallback_enabled():', press)
        self.assertIn('if not self._hud_fallback_enabled():', release)

    def test_widget_mode_removes_shell_outline(self):
        self.assertIn('#container[widgetMode="true"]', SOURCE)
        self.assertIn('self.main_container.setProperty("widgetMode", self.widget_mode)', SOURCE)

    def test_navigation_closes_voice_mode_without_blocking_gui(self):
        self.assertIn('self._stop_voice_mode_for_navigation("смене раздела")', SOURCE)
        self.assertIn('self._stop_voice_mode_for_navigation("смене диалога")', SOURCE)
        helper = SOURCE.split('def _stop_voice_mode_for_navigation', 1)[1].split(
            'def _sync_voice_mode_overlay', 1
        )[0]
        self.assertIn('"voice-session-stop"', helper)
        self.assertNotIn('requests.post(', helper)

    def test_settings_buttons_share_provider_action_visual_language(self):
        settings_button_style = SOURCE.split('#settingsPage QPushButton{', 1)[1].split('}', 1)[0]
        self.assertIn('background:transparent;', settings_button_style)
        self.assertIn('border:1px solid #00aaff;', settings_button_style)
        self.assertIn('border-radius:9px;', settings_button_style)
        history_button_style = SOURCE.split('#historyRefresh{', 1)[1].split('}', 1)[0]
        self.assertIn('background:transparent;', history_button_style)
        self.assertIn('border:1px solid #00aaff;', history_button_style)

    def test_history_chat_rows_use_spaced_glass_cards(self):
        self.assertIn('self.history_list.setSpacing(6)', SOURCE)
        self.assertIn('self.history_list.viewport().setObjectName("historyListViewport")', SOURCE)
        self.assertNotIn('self.history_list.viewport().setStyleSheet', SOURCE)
        self.assertIn('QWidget#historyRow{', SOURCE)
        self.assertIn('background:rgba(8,12,14,185);', SOURCE)
        self.assertIn('border-radius:14px;', SOURCE)
        self.assertIn('QWidget#historyRow[active="true"]', SOURCE)
        history_apply = SOURCE.split('def _apply_history_sessions', 1)[1].split(
            'def open_history_chat', 1
        )[0]
        self.assertNotIn('row.setStyleSheet', history_apply)
        self.assertIn('row.setProperty(', history_apply)
        self.assertIn('row_layout.setContentsMargins(16, 9, 16, 9)', history_apply)

    def test_ready_chat_status_never_uses_a_transient_green_success_state(self):
        finished = SOURCE.split('def _chat_request_finished', 1)[1].split(
            'def _chat_request_failed', 1
        )[0]
        self.assertNotIn('#32c875', finished)
        self.assertIn('#00aaff', finished)

    def test_settings_sections_share_bottom_action_row(self):
        section = SOURCE.split('def section_page(', 1)[1].split('general_page = QFrame()', 1)[0]
        self.assertIn('content_layout = QVBoxLayout(content_host)', section)
        self.assertIn('page_layout.addWidget(content_host, 1)', section)
        self.assertIn('footer_layout = QHBoxLayout()', section)
        self.assertIn('extra_builder(content_layout, edits, footer_layout)', section)
        self.assertIn('page_layout.addLayout(footer_layout)', section)
        self.assertIn('content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)', section)
        self.assertIn('layout.addWidget(command_view, 1)', SOURCE)
        self.assertIn('command_view.setSpacing(5)', SOURCE)
        self.assertIn('actions.addWidget(edit_button)', SOURCE)
        self.assertIn('voice_layout.addStretch(1)', SOURCE)
        self.assertIn('history_layout.addWidget(self.history_list, 1)', SOURCE)
        self.assertIn('history_layout.addLayout(history_actions)', SOURCE)

    def test_chat_web_surface_has_opaque_dpi_seam_backing(self):
        self.assertIn('self.chat_view.page().setBackgroundColor(QColor("#121212"))', SOURCE)
        self.assertIn('class OpaqueWebSurface(QFrame):', SOURCE)
        self.assertIn('self.setObjectName("chatWebSurface")', SOURCE)
        self.assertIn('self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)', SOURCE)
        self.assertIn('QFrame#chatWebSurface{background:#121212; border:none;}', SOURCE)
        self.assertIn('self._view.setGeometry(0, 0, self.width() + bleed, self.height() + bleed)', SOURCE)
        self.assertIn('self.chat_surface = OpaqueWebSurface(self.chat_view)', SOURCE)
        self.assertIn('chat_layout.setSpacing(0)', SOURCE)
        self.assertIn('self.chat_composer_guard.setFixedHeight(20)', SOURCE)
        self.assertIn('QFrame#chatComposerGuard{background:#121212; border:none;}', SOURCE)
        self.assertIn('#chatWebSurface,', SOURCE)
        self.assertIn('html {', CHAT_HTML)
        self.assertIn('background: var(--bg-main);', CHAT_HTML)
        self.assertIn('gap: 14px; background: var(--bg-main);', CHAT_HTML)
        self.assertIn('*::-webkit-scrollbar-track { background: var(--bg-main); }', CHAT_HTML)
        self.assertNotIn('*::-webkit-scrollbar-track { background: transparent; }', CHAT_HTML)

    def test_start_button_never_draws_a_square_focus_frame(self):
        self.assertIn('self.setFocusPolicy(Qt.FocusPolicy.NoFocus)', SOURCE)
        self.assertIn('self.setAutoDefault(False)', SOURCE)
        self.assertIn('option.state &= ~QStyle.StateFlag.State_HasFocus', SOURCE)
        self.assertIn('#jarvisStart:focus{', SOURCE)
        self.assertIn('outline:none;', SOURCE)


if __name__ == "__main__":
    unittest.main()
