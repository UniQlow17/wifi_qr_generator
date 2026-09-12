"""Main desktop window for the Wi-Fi QR Generator app."""
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..core import printing, storage, updater, wifi_detect
from ..core.qr_generator import generate_wifi_qr_image
from .permission_dialog import PermissionDialog
from .update_dialog import UpdateDialog

ENCRYPTION_OPTIONS = [("WPA/WPA2", "WPA"), ("WEP", "WEP"), ("Без пароля", "nopass")]
PREVIEW_SIZE = (280, 280)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.title("Wi-Fi QR Generator")
        self.geometry("480x700")
        self.minsize(420, 620)

        self._qr_image = None
        self._password_visible = False
        # SSIDs the OS reported as "known" this session — only these are
        # eligible for on-demand password lookup when picked from the
        # dropdown (typing an unrelated new SSID must never trigger it).
        self._known_ssids = set()

        self._build_ui()
        self._refresh_ssid_values()

        # Deferred so the window is visible before the dialog pops up.
        self.after(300, self._maybe_offer_detection)

    def _build_ui(self):
        container = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            container, text="Wi-Fi QR Generator", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=(0, 24))

        ctk.CTkLabel(container, text="SSID (имя сети):", anchor="w").pack(fill="x")
        self.ssid_combo = ctk.CTkComboBox(container, values=[], command=self._on_ssid_selected)
        self.ssid_combo.set("")
        self.ssid_combo.pack(fill="x", pady=(4, 16))

        ctk.CTkLabel(container, text="Пароль:", anchor="w").pack(fill="x")
        password_row = ctk.CTkFrame(container, fg_color="transparent")
        password_row.pack(fill="x", pady=(4, 16))
        self.password_entry = ctk.CTkEntry(password_row, show="*")
        self.password_entry.pack(side="left", fill="x", expand=True)
        self.toggle_password_btn = ctk.CTkButton(
            password_row, text="Показать", width=90, command=self._toggle_password
        )
        self.toggle_password_btn.pack(side="left", padx=(8, 0))

        ctk.CTkLabel(container, text="Тип шифрования:", anchor="w").pack(fill="x")
        self.encryption_menu = ctk.CTkOptionMenu(
            container, values=[label for label, _ in ENCRYPTION_OPTIONS]
        )
        self.encryption_menu.pack(fill="x", pady=(4, 24))

        self.generate_btn = ctk.CTkButton(
            container, text="Сгенерировать QR-код", command=self._on_generate
        )
        self.generate_btn.pack(fill="x", pady=(0, 20))

        self.qr_label = ctk.CTkLabel(
            container, text="QR-код появится здесь", width=PREVIEW_SIZE[0], height=PREVIEW_SIZE[1]
        )
        self.qr_label.pack(pady=(0, 16))

        action_row = ctk.CTkFrame(container, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 12))
        self.save_btn = ctk.CTkButton(
            action_row, text="Сохранить как PNG", command=self._on_save, state="disabled"
        )
        self.save_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.print_btn = ctk.CTkButton(
            action_row, text="Печать", command=self._on_print, state="disabled"
        )
        self.print_btn.pack(side="left", fill="x", expand=True, padx=(6, 0))

        self.status_label = ctk.CTkLabel(container, text="", text_color="gray", wraplength=380)
        self.status_label.pack(pady=(0, 10))

    def _toggle_password(self):
        self._password_visible = not self._password_visible
        self.password_entry.configure(show="" if self._password_visible else "*")
        self.toggle_password_btn.configure(text="Скрыть" if self._password_visible else "Показать")

    def _refresh_ssid_values(self):
        ssids = storage.load_ssids()
        self.ssid_combo.configure(values=ssids)
        if ssids and not self.ssid_combo.get():
            self.ssid_combo.set(ssids[0])

    def _maybe_offer_detection(self):
        if storage.load_ssids():
            self._check_for_update()
            return
        PermissionDialog(self, on_decision=self._on_permission_decision)

    def _on_permission_decision(self, allowed):
        # Deferred until the permission dialog (if any) has closed, so the
        # two modal dialogs never fight over the window grab.
        self._check_for_update()
        if not allowed:
            return
        self.status_label.configure(text="Определяем сети Wi-Fi этого компьютера...")
        threading.Thread(target=self._detect_wifi_worker, daemon=True).start()

    def _check_for_update(self):
        threading.Thread(target=self._check_for_update_worker, daemon=True).start()

    def _check_for_update_worker(self):
        result = updater.check_for_update()
        if result:
            tag_name, asset = result
            self.after(0, lambda: self._offer_update(tag_name, asset))

    def _offer_update(self, tag_name, asset):
        UpdateDialog(
            self,
            latest_version=tag_name,
            on_decision=lambda accepted, dialog: self._on_update_decision(accepted, dialog, asset),
        )

    def _on_update_decision(self, accepted, dialog, asset):
        if not accepted:
            return
        threading.Thread(
            target=self._download_update_worker, args=(dialog, asset), daemon=True
        ).start()

    def _download_update_worker(self, dialog, asset):
        def on_progress(downloaded, total):
            self.after(0, lambda: dialog.set_progress(downloaded / total))

        try:
            updater.download_and_relaunch(asset, on_progress=on_progress)
        except Exception as exc:
            self.after(0, lambda: dialog.show_error(str(exc)))
            return

        self.after(0, self.destroy)

    def _detect_wifi_worker(self):
        ssid, password = wifi_detect.detect_current_wifi()
        known_ssids = wifi_detect.list_known_networks()
        self.after(0, lambda: self._apply_detected(ssid, password, known_ssids))

    def _apply_detected(self, ssid, password, known_ssids):
        for known_ssid in known_ssids:
            self._known_ssids.add(known_ssid)
            storage.save_ssid(known_ssid)
        self._refresh_ssid_values()

        if ssid:
            self.ssid_combo.set(ssid)
        if password:
            self.password_entry.delete(0, "end")
            self.password_entry.insert(0, password)

        if ssid:
            text = "Текущая сеть определена автоматически."
        elif known_ssids:
            text = f"Найдено известных сетей: {len(known_ssids)}. Выберите нужную из списка."
        else:
            text = "Не удалось определить сети. Введите данные вручную."
        self.status_label.configure(text=text)

    def _on_ssid_selected(self, choice):
        # Only known-from-OS SSIDs are eligible for lookup — never fires for
        # freshly typed text, so it can't clobber a password mid-typing.
        if choice not in self._known_ssids:
            return
        self.status_label.configure(text=f"Ищем сохранённый пароль для «{choice}»...")
        threading.Thread(target=self._fetch_password_worker, args=(choice,), daemon=True).start()

    def _fetch_password_worker(self, ssid):
        password = wifi_detect.get_saved_password(ssid)
        self.after(0, lambda: self._apply_fetched_password(ssid, password))

    def _apply_fetched_password(self, ssid, password):
        if self.ssid_combo.get() != ssid:
            return  # user already moved on to something else
        self.password_entry.delete(0, "end")
        if password:
            self.password_entry.insert(0, password)
            self.status_label.configure(text=f"Пароль для «{ssid}» найден.")
        else:
            self.status_label.configure(
                text=(
                    f"Пароль для «{ssid}» недоступен без прав администратора "
                    "(ОС хранит его в защищённом виде для неактивных сетей). "
                    "Введите вручную."
                )
            )

    def _on_generate(self):
        ssid = self.ssid_combo.get().strip()
        if not ssid:
            messagebox.showwarning("Нужен SSID", "Введите имя сети (SSID).")
            return

        password = self.password_entry.get()
        selected_label = self.encryption_menu.get()
        encryption = next(
            code for label, code in ENCRYPTION_OPTIONS if label == selected_label
        )

        try:
            image = generate_wifi_qr_image(ssid, password, encryption)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось сгенерировать QR-код: {exc}")
            return

        self._qr_image = image

        preview = image.copy()
        preview.thumbnail(PREVIEW_SIZE)
        ctk_image = ctk.CTkImage(light_image=preview, dark_image=preview, size=preview.size)
        self.qr_label.configure(image=ctk_image, text="")
        self.qr_label.image = ctk_image

        self.save_btn.configure(state="normal")
        self.print_btn.configure(state="normal")

        storage.save_ssid(ssid)
        self._refresh_ssid_values()
        self.ssid_combo.set(ssid)
        self.status_label.configure(text="QR-код сгенерирован.")

    def _on_save(self):
        if self._qr_image is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
            initialfile="wifi_qr_code.png",
        )
        if not path:
            return
        try:
            self._qr_image.save(path)
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось сохранить файл: {exc}")
            return
        self.status_label.configure(text=f"Сохранено: {path}")

    def _on_print(self):
        if self._qr_image is None:
            return
        try:
            printing.print_image(self._qr_image)
        except Exception as exc:
            messagebox.showerror("Ошибка печати", str(exc))


def run():
    app = App()
    app.mainloop()
