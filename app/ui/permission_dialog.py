"""A one-click consent dialog shown before the app reads the OS's current
Wi-Fi network info, instead of silently reaching into OS-level Wi-Fi
credentials on the user's behalf without asking."""
import customtkinter as ctk


class PermissionDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_decision):
        super().__init__(parent)
        self._on_decision = on_decision

        self.title("Разрешение")
        self.geometry("420x240")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._skip)

        ctk.CTkLabel(
            self,
            text=(
                "Список сохранённых сетей пуст.\n\n"
                "Разрешить приложению один раз прочитать список всех "
                "Wi-Fi сетей, известных этой операционной системе (имена "
                "и, при выборе сети, её пароль), чтобы не вводить их "
                "вручную?\n\n"
                "Данные не покидают ваш компьютер."
            ),
            wraplength=380,
            justify="left",
        ).pack(padx=20, pady=(20, 10), fill="both", expand=True)

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(pady=(0, 20))

        ctk.CTkButton(button_row, text="Разрешить", command=self._allow).pack(
            side="left", padx=10
        )
        ctk.CTkButton(
            button_row,
            text="Пропустить",
            fg_color="transparent",
            border_width=1,
            command=self._skip,
        ).pack(side="left", padx=10)

        # Grabbing focus only after the window is actually mapped avoids a
        # "grab failed: window not viewable" error on some platforms.
        self.after(50, self.grab_set)

    def _allow(self):
        self._finish(True)

    def _skip(self):
        self._finish(False)

    def _finish(self, allowed):
        self.grab_release()
        self.destroy()
        self._on_decision(allowed)
