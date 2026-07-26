import json
import datetime
import os
import time
import flet as ft
import flet_camera as fc
from plyer import notification

JSON_FILE = "receipts.json"
IMG_DIR = "receipt_images"
PURPLE = "#6C5CE7"
BG_CARD = "#1E1E2E"

os.makedirs(IMG_DIR, exist_ok=True)


# ---------------- DATA STORAGE ----------------
def load_receipts():
    try:
        with open(JSON_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_receipts(data):
    with open(JSON_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ---------------- DATE CALCULATIONS ----------------
def calculate_days_remaining(exp_str):
    if not exp_str or exp_str == "None":
        return None, "No Return"
    try:
        exp_date = datetime.datetime.strptime(exp_str, "%Y-%m-%d").date()
        days = (exp_date - datetime.date.today()).days
        if days < 0:
            return days, "Expired"
        if days == 0:
            return days, "Expires Today!"
        return days, f"{days} Days Left"
    except Exception:
        return None, "N/A"


def calculate_reminder(days, today):
    if days <= 0:
        return "None", "None"
    notify_before = 3 if days <= 7 else 5 if days <= 30 else 7 if days <= 90 else 14
    exp = today + datetime.timedelta(days=days)
    notify = exp - datetime.timedelta(days=notify_before)
    return str(exp), str(notify)


# ---------------- ANDROID NOTIFICATIONS ----------------
def send_android_notification(title, message):
    """Triggers native Android status bar banner via Plyer."""
    try:
        notification.notify(
            title=title,
            message=message,
            app_name="SnapReceipt",
            timeout=10,
        )
    except Exception as ex:
        print(f"Notification Error: {ex}")


def check_and_trigger_due_notifications():
    """Scans receipts upon app launch for Return or Warranty reminders due TODAY."""
    today_str = str(datetime.date.today())
    receipts = load_receipts()

    for item in receipts:
        shop = item.get("shop", "Unknown Shop")

        # 1. Check Return Notification
        if item.get("return_notification_date") == today_str:
            exp_date = item.get("return_expiration", "")
            send_android_notification(
                title=f"Return Window Alert: {shop}",
                message=f"Return window is expiring on {exp_date}! Don't forget your receipt.",
            )

        # 2. Check Warranty Notification
        if item.get("warranty_notification_date") == today_str:
            exp_date = item.get("warranty_expiration", "")
            send_android_notification(
                title=f"Warranty Expiring Soon: {shop}",
                message=f"Warranty coverage ends on {exp_date}. Check your item status.",
            )


# ---------------- MAIN APP ----------------
async def main(page: ft.Page):
    page.title = "SnapReceipt"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 15

    captured_pages = []
    camera_state = {"ready": False}

    camera = fc.Camera(expand=True)
    scan_status = ft.Text("Initializing camera...", size=12, color=ft.Colors.GREY_400)
    pages_text = ft.Text("", size=11, color=ft.Colors.PURPLE_200)
    feedback_text = ft.Text("", size=12)

    shop_input = ft.TextField(
        label="Shop / Brand Name", bgcolor=BG_CARD, border_radius=10
    )
    desc_input = ft.TextField(
        label="Description / Serial Notes",
        multiline=True,
        bgcolor=BG_CARD,
        border_radius=10,
    )
    cat_dropdown = ft.Dropdown(
        label="Category",
        value="Electronics",
        options=[
            ft.dropdown.Option(o)
            for o in ["Electronics", "Appliances", "Clothing", "Groceries", "Other"]
        ],
        bgcolor=BG_CARD,
        expand=True,
    )
    return_dropdown = ft.Dropdown(
        label="Return Window",
        value="7 Days",
        options=[
            ft.dropdown.Option(o)
            for o in ["7 Days", "14 Days", "30 Days", "90 Days", "None"]
        ],
        bgcolor=BG_CARD,
        expand=True,
    )
    warranty_dropdown = ft.Dropdown(
        label="Warranty",
        value="1 Year",
        options=[
            ft.dropdown.Option(o)
            for o in ["No Warranty", "7 Days", "30 Days", "1 Year", "2 Years"]
        ],
        bgcolor=BG_CARD,
    )

    def show_receipt_details(item):
        pages = item.get("pages_captured", [])
        dlg = ft.AlertDialog(
            title=ft.Text(item.get("shop", "Receipt")),
            content=ft.Column(
                [
                    ft.Text(f"Description: {item.get('description', 'N/A')}"),
                    ft.Text(f"Category: {item.get('category')}"),
                    ft.Text(f"Added: {item.get('created_date')}"),
                    ft.Text(
                        f"Return: {item.get('return_window')} (Expires: {item.get('return_expiration')})"
                    ),
                    ft.Text(f"Return Notif: {item.get('return_notification_date')}"),
                    ft.Text(
                        f"Warranty: {item.get('warranty')} (Expires: {item.get('warranty_expiration')})"
                    ),
                    ft.Text(
                        f"Warranty Notif: {item.get('warranty_notification_date')}"
                    ),
                    ft.Row(
                        [
                            ft.Image(
                                src=p,
                                width=80,
                                height=80,
                                fit=ft.BoxFit.COVER,
                                border_radius=8,
                            )
                            for p in pages
                        ],
                        scroll=ft.ScrollMode.AUTO,
                    ),
                ],
                tight=True,
                spacing=6,
            ),
            actions=[ft.TextButton("Close", on_click=lambda _: page.pop_dialog())],
        )
        page.show_dialog(dlg)

    vault_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    def delete_receipt(rid):
        receipts = load_receipts()
        target = next((r for r in receipts if r.get("id") == rid), None)
        if target:
            for p in target.get("pages_captured", []):
                try:
                    os.remove(p)
                except OSError:
                    pass
        save_receipts([r for r in receipts if r.get("id") != rid])
        refresh_vault()

    def refresh_vault():
        vault_list.controls.clear()
        receipts = load_receipts()
        if not receipts:
            vault_list.controls.append(
                ft.Text("Vault is empty.", color=ft.Colors.GREY_500)
            )
        for item in receipts:
            _, badge = calculate_days_remaining(item.get("return_expiration"))
            vault_list.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        item.get("shop", "Unknown"),
                                        weight=ft.FontWeight.BOLD,
                                        size=16,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE,
                                        icon_color=ft.Colors.RED_400,
                                        on_click=lambda _, r=item.get(
                                            "id"
                                        ): delete_receipt(r),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(
                                f"Return: {badge} | Warranty: {item.get('warranty')}",
                                size=12,
                                color=ft.Colors.GREY_400,
                            ),
                        ]
                    ),
                    bgcolor=BG_CARD,
                    padding=10,
                    border_radius=10,
                    on_click=lambda _, i=item: show_receipt_details(i),
                )
            )
        page.update()

    async def ensure_camera():
        if camera_state["ready"]:
            return True
        try:
            cams = await camera.get_available_cameras()
            if not cams:
                scan_status.value = "No camera found"
                page.update()
                return False
            chosen = next(
                (c for c in cams if c.lens_direction == fc.CameraLensDirection.BACK),
                cams[0],
            )
            await camera.initialize(
                description=chosen,
                resolution_preset=fc.ResolutionPreset.MEDIUM,
                enable_audio=False,
            )
            camera_state["ready"] = True
            scan_status.value = "Align receipt in frame"
            page.update()
            return True
        except Exception as ex:
            scan_status.value = f"Camera error: {ex}"
            page.update()
            return False

    async def capture_photo(e):
        if not await ensure_camera():
            return
        data = await camera.take_picture()
        path = os.path.join(IMG_DIR, f"receipt_{int(time.time() * 1000)}.jpg")
        with open(path, "wb") as f:
            f.write(data)
        captured_pages.append(path)
        scan_status.value = f"Captured {len(captured_pages)} page(s)"
        pages_text.value = f"{len(captured_pages)} page(s) attached"
        page.update()

    def clear_pages(e):
        for p in captured_pages:
            try:
                os.remove(p)
            except OSError:
                pass
        captured_pages.clear()
        pages_text.value = ""
        scan_status.value = "Align receipt in frame"
        page.update()

    def save_receipt(e):
        if not shop_input.value.strip():
            feedback_text.value = "Shop name required."
            feedback_text.color = ft.Colors.RED_400
            page.update()
            return

        today = datetime.date.today()
        ret_days = {
            "7 Days": 7,
            "14 Days": 14,
            "30 Days": 30,
            "90 Days": 90,
            "None": 0,
        }.get(return_dropdown.value, 0)
        war_days = {
            "7 Days": 7,
            "30 Days": 30,
            "1 Year": 365,
            "2 Years": 730,
            "No Warranty": 0,
        }.get(warranty_dropdown.value, 0)

        ret_exp, ret_notif = calculate_reminder(ret_days, today)
        war_exp, war_notif = calculate_reminder(war_days, today)

        data = load_receipts()
        data.insert(
            0,
            {
                "id": int(datetime.datetime.now().timestamp()),
                "shop": shop_input.value.strip(),
                "description": desc_input.value.strip(),
                "category": cat_dropdown.value,
                "pages_captured": list(captured_pages),
                "total_pages": max(1, len(captured_pages)),
                "created_date": str(today),
                "return_window": return_dropdown.value,
                "return_expiration": ret_exp,
                "return_notification_date": ret_notif,
                "warranty": warranty_dropdown.value,
                "warranty_expiration": war_exp,
                "warranty_notification_date": war_notif,
            },
        )
        save_receipts(data)

        shop_input.value = ""
        desc_input.value = ""
        captured_pages.clear()
        pages_text.value = ""
        feedback_text.value = "Saved successfully!"
        feedback_text.color = ft.Colors.GREEN_400

        nav.selected_index = 0
        add_view.visible = False
        vault_view.visible = True
        refresh_vault()

    vault_view = ft.Column(
        [ft.Text("Vault", size=20, weight=ft.FontWeight.BOLD), vault_list], expand=True
    )

    scan_box = ft.Container(
        content=ft.Stack(
            [
                camera,
                ft.Container(
                    content=ft.Column(
                        [
                            ft.IconButton(
                                icon=ft.Icons.CAMERA_ALT,
                                bgcolor=PURPLE,
                                icon_color="white",
                                on_click=capture_photo,
                            ),
                            scan_status,
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    alignment=ft.Alignment.BOTTOM_CENTER,
                    padding=10,
                ),
            ]
        ),
        height=250,
        bgcolor="black",
        border_radius=10,
    )

    add_view = ft.Column(
        [
            ft.Text("Add Receipt", size=20, weight=ft.FontWeight.BOLD),
            scan_box,
            ft.Row(
                [pages_text, ft.TextButton("Clear", on_click=clear_pages)],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            shop_input,
            desc_input,
            ft.Row([cat_dropdown, return_dropdown]),
            warranty_dropdown,
            ft.ElevatedButton(
                "Save Receipt", bgcolor=PURPLE, color="white", on_click=save_receipt
            ),
            feedback_text,
        ],
        scroll=ft.ScrollMode.AUTO,
        visible=False,
        expand=True,
    )

    async def on_nav_change(e):
        is_add = e.control.selected_index == 1
        add_view.visible = is_add
        vault_view.visible = not is_add
        page.update()
        if is_add:
            await ensure_camera()
        else:
            refresh_vault()

    nav = ft.NavigationBar(
        selected_index=0,
        on_change=on_nav_change,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.INVENTORY_2, label="Vault"),
            ft.NavigationBarDestination(icon=ft.Icons.ADD_A_PHOTO, label="Add"),
        ],
    )

    page.add(ft.Stack([vault_view, add_view], expand=True))
    page.navigation_bar = nav
    refresh_vault()

    # Check and trigger pending notifications upon launch
    check_and_trigger_due_notifications()


if __name__ == "__main__":
    ft.run(main)
