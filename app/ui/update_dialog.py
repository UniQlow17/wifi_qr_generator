"""Dialog offering to download and install a newer release, with a
one-click confirmation instead of updating silently in the background."""
import customtkinter as ctk

from ..version import __version__


class UpdateDialog(ctk.CTkToplevel):
    def __init__(self, parent, latest_version, on_decision):
        super().__init__(parent)
        self._on_decision = on_decision

        self.title("Доступно обновление")
        self.geometry("420x260")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._later)

        self._message_label = ctk.CTkLabel(
            self,
            text=(
                f"Доступна новая версия: {latest_version}\n"
                f"Установлена версия: {__version__}\n\n"
                "Скачать и установить обновление? Приложение перезапустится "
                "автоматически с новой версией."
            ),
            wraplength=380,
            justify="left",
        )
        self._message_label.pack(padx=20, pady=(20, 10), fill="both", expand=True)

        self._progress_bar = ctk.CTkProgressBar(self)
        self._progress_bar.set(0)

        self._button_row = ctk.CTkFrame(self, fg_color="transparent")
        self._button_row.pack(pady=(0, 20))

        self._update_btn = ctk.CTkButton(self._button_row, text="Обновить", command=self._update)
        self._update_btn.pack(side="left", padx=10)

        self._later_btn = ctk.CTkButton(
            self._button_row,
            text="Позже",
            fg_color="transparent",
            border_width=1,
            command=self._later,
        )
        self._later_btn.pack(side="left", padx=10)

        self.after(50, self.grab_set)

    def _update(self):
        self._update_btn.configure(state="disabled")
        self._later_btn.configure(state="disabled")
        self._message_label.configure(text="Скачивание обновления...")
        self._progress_bar.pack(padx=20, pady=(0, 20), fill="x")
        self._on_decision(True, self)

    def _later(self):
        self.grab_release()
        self.destroy()
        self._on_decision(False, None)

    def set_progress(self, fraction):
        self._progress_bar.set(fraction)

    def show_error(self, message):
        self._message_label.configure(text=message)
        self._progress_bar.pack_forget()
        self._later_btn.configure(text="Закрыть", state="normal")
