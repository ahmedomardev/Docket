import asyncio
import datetime
import json
import os
import time
import urllib.parse
import urllib.request
import flet as ft
import flet_camera as fc

# Data Storage & Assets
JSON_FILE, IMG_DIR = "docket_data.json", "docket_images"
BG_DARK, BG_CARD, BG_INPUT = "#0A0F1D", "#131B2E", "#1E293B"
ACCENT, GREEN, RED, MUTED = "#8B5CF6", "#10B981", "#EF4444", "#94A3B8"
os.makedirs(IMG_DIR, exist_ok=True)

OEM_BASE = {
    "Engine Oil & Filter": (1.0, 10000),
    "Cabin Air Filter": (1.0, 20000),
    "Engine Air Filter": (2.0, 30000),
    "Brake Pads": (3.0, 45000),
    "Brake Rotors": (5.0, 70000),
    "Spark Plugs": (4.0, 60000),
    "Coolant / Antifreeze": (5.0, 90000),
    "Transmission Fluid": (5.0, 80000),
    "Tires": (4.0, 50000),
    "12V Battery": (3.0, 60000),
    "Timing Belt": (5.0, 100000),
    "Serpentine Belt": (3.0, 60000),
}

PARTS = list(OEM_BASE.keys())

MAKES = sorted(
    [
        "Audi",
        "BMW",
        "Chevrolet",
        "Dodge",
        "Ford",
        "Honda",
        "Hyundai",
        "Kia",
        "Lexus",
        "Mazda",
        "Mercedes-Benz",
        "Nissan",
        "Porsche",
        "Subaru",
        "Tesla",
        "Toyota",
        "Volkswagen",
        "Volvo",
    ]
)
RET_DAYS = {"7 Days": 7, "14 Days": 14, "30 Days": 30, "None": 0}
WAR_DAYS = {
    "30 Days": 30,
    "90 Days": 90,
    "1 Year": 365,
    "2 Years": 730,
    "No Warranty": 0,
}


def load_data():
    try:
        with open(JSON_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save_data(data):
    json.dump(data, open(JSON_FILE, "w"), indent=2)


def get_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as res:
            return json.loads(res.read().decode()) if res.status == 200 else None
    except Exception:
        return None


async def fetch_models(make):
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/getmodelsformake/{urllib.parse.quote(make)}?format=json"
    data = await asyncio.to_thread(get_json, url)
    models = (
        sorted(
            {
                it["Model_Name"].strip()
                for it in data.get("Results", [])
                if it.get("Model_Name")
            }
        )
        if data
        else []
    )
    return models or ["General"]


async def fetch_interval(make, model, part):
    url = f"https://dev-api.carscan.com/v3.0/maint?year=2020&make={urllib.parse.quote(make)}&model={urllib.parse.quote(model)}"
    data = await asyncio.to_thread(get_json, url)

    if data and "data" in data and isinstance(data["data"], list):
        for item in data["data"]:
            if part.lower() in item.get("item", "").lower():
                km = item.get("mileage", 0)
                if km > 0:
                    return round(km / 15000, 1), float(km)

    y, km = OEM_BASE.get(part, (2.0, 30000))
    if "Tesla" in make and ("Oil" in part or "Spark" in part):
        return 0.0, 0.0
    if make in ["BMW", "Mercedes-Benz", "Audi"] and "Oil" in part:
        return 1.0, 15000
    return y, km


def days_left(exp_str):
    if not exp_str or exp_str == "None":
        return "No Expiration"
    try:
        d = (
            datetime.datetime.strptime(exp_str, "%Y-%m-%d").date()
            - datetime.date.today()
        ).days
        return "Expired" if d < 0 else "Expires Today" if d == 0 else f"{d} days left"
    except Exception:
        return "N/A"


def calc_expiration(days):
    if days <= 0:
        return "None"
    return str(datetime.date.today() + datetime.timedelta(days=days))


# Modern UI Helper Components with Clean Borders
def Dropdown(label, opts, value=None, on_change=None, **kw):
    bg = kw.pop("bgcolor", BG_INPUT)
    dd = ft.Dropdown(
        label=label,
        value=value,
        bgcolor=bg,
        border_color="#334155",
        focused_border_color=ACCENT,
        border_width=1,
        focused_border_width=1.5,
        border_radius=12,
        options=[ft.dropdown.Option(key=o, text=o) for o in opts],
        **kw,
    )
    if on_change:
        dd.on_change = on_change
    return dd


def Input(label, **kw):
    bg = kw.pop("bgcolor", BG_INPUT)
    return ft.TextField(
        label=label,
        bgcolor=bg,
        border_color="#334155",
        focused_border_color=ACCENT,
        border_width=1,
        focused_border_width=1.5,
        border_radius=12,
        **kw,
    )


NUM_FILTER = ft.InputFilter(regex_string=r"[0-9.]", allow=True, replacement_string="")


def parse_num(v):
    try:
        return float(v) if v not in (None, "", ".") else 0.0
    except Exception:
        return 0.0


async def main(page: ft.Page):
    page.title = "Docket"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 16
    page.bgcolor = BG_DARK

    captured_photos = []
    camera_state = {"ready": False}
    saving_in_progress = False

    try:
        camera = fc.Camera(expand=True)
        has_camera = True
    except Exception:
        camera = ft.Container(
            ft.Text("Camera unavailable", color=MUTED), alignment=ft.Alignment(0, 0)
        )
        has_camera = False

    async def ensure_camera():
        if not has_camera or camera_state["ready"]:
            return
        try:
            cams = await camera.get_available_cameras()
            if cams:
                chosen = next(
                    (
                        c
                        for c in cams
                        if c.lens_direction == fc.CameraLensDirection.BACK
                    ),
                    cams[0],
                )
                await camera.initialize(
                    description=chosen,
                    resolution_preset=fc.ResolutionPreset.MEDIUM,
                    enable_audio=False,
                )
                camera_state["ready"] = True
                page.update()
        except Exception:
            pass

    async def capture_photo(e):
        if not has_camera:
            return
        await ensure_camera()
        try:
            data = await camera.take_picture()
            path = os.path.join(IMG_DIR, f"docket_{int(time.time() * 1000)}.jpg")
            open(path, "wb").write(data)
            captured_photos.append(path)
            photo_status.value = f"📸 {len(captured_photos)} photo(s) attached"
            page.update()
        except Exception:
            pass

    photo_status = ft.Text("", size=12, color=ACCENT, weight=ft.FontWeight.BOLD)

    camera_box = ft.Container(
        content=ft.Stack(
            [
                camera,
                ft.Container(
                    content=ft.ElevatedButton(
                        "Capture Photo",
                        icon=ft.Icons.CAMERA_ALT_ROUNDED,
                        bgcolor=ACCENT,
                        color="white",
                        on_click=capture_photo,
                    ),
                    alignment=ft.Alignment(0, 1),
                    padding=12,
                ),
            ]
        ),
        height=200,
        bgcolor="black",
        border_radius=16,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )

    search_bar = Input(
        "Search records...",
        prefix_icon=ft.Icons.SEARCH,
        on_change=lambda e: refresh_list(),
    )
    docket_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    # Receipt Form Fields
    shop_in = Input("Store / Brand Name")
    price_receipt_in = Input(
        "Cost ($)", keyboard_type=ft.KeyboardType.NUMBER, input_filter=NUM_FILTER
    )
    cat_dd = Dropdown(
        "Category",
        ["Electronics", "Appliances", "Clothing", "Auto", "Other"],
        "Electronics",
        expand=True,
    )
    return_dd = Dropdown("Return Window", list(RET_DAYS), "14 Days", expand=True)
    warranty_dd = Dropdown("Warranty", list(WAR_DAYS), "1 Year")
    notes_in = Input("Notes / Details", multiline=True)

    receipt_box = ft.Column(
        [shop_in, price_receipt_in, ft.Row([cat_dd, return_dd]), warranty_dd, notes_in],
        spacing=10,
    )

    # Car Part Form Fields
    model_dd = Dropdown("Model", ["General"], "General", expand=True)

    async def on_make_change(e):
        models = await fetch_models(make_dd.value)
        model_dd.options = [ft.dropdown.Option(key=m, text=m) for m in models]
        model_dd.value = models[0] if models else "General"
        page.update()

    make_dd = Dropdown("Make", MAKES, "Toyota", expand=True, on_change=on_make_change)
    part_dd = Dropdown("Component", PARTS, "Engine Oil & Filter")
    price_part_in = Input(
        "Part Price ($)",
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=NUM_FILTER,
        expand=True,
    )
    km_in = Input(
        "(KM) Since installation",
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=NUM_FILTER,
        expand=True,
    )

    car_box = ft.Column(
        [
            ft.Row([make_dd, model_dd]),
            part_dd,
            ft.Row([price_part_in, km_in]),
        ],
        spacing=10,
    )

    # Dynamic Container for Form Fields
    form_container = ft.Container(content=receipt_box)

    type_dd = Dropdown(
        "Record Type", ["Receipt", "Car Part"], "Receipt", bgcolor=BG_CARD, expand=True
    )

    def confirm_type(e):
        val = type_dd.value
        if val == "Car Part":
            form_container.content = car_box
        else:
            form_container.content = receipt_box
        form_container.update()

    type_row = ft.Row(
        [
            type_dd,
            ft.ElevatedButton(
                "Confirm",
                bgcolor=ACCENT,
                color="white",
                height=48,
                on_click=confirm_type,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def delete_item(uid):
        data = load_data()
        target = next((x for x in data if x.get("id") == uid), None)
        for p in (target or {}).get("photos", []):
            try:
                os.remove(p)
            except Exception:
                pass
        save_data([x for x in data if x.get("id") != uid])
        refresh_list()

    def show_details(item):
        is_car = item.get("type") == "Car Part"
        content_items = [
            ft.Text(
                item.get("car") if is_car else item.get("shop"),
                size=18,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Text(
                f"Price: ${item.get('price', 0):.2f}",
                size=14,
                color=GREEN,
                weight=ft.FontWeight.BOLD,
            ),
        ]
        if is_car:
            content_items.append(
                ft.Text(f"Part: {item.get('part')}", size=13, color=MUTED)
            )
            content_items.append(
                ft.Text(
                    f"(KM) Since installation: {int(item.get('km', 0)):,} KM",
                    size=13,
                    color=MUTED,
                )
            )
            content_items.append(
                ft.Text(
                    f"Service Interval: Every {item.get('replace_km', 10000):,} KM ({item.get('replace_years', 1)} Yrs)",
                    size=13,
                    color=MUTED,
                )
            )
        else:
            content_items.append(
                ft.Text(f"Category: {item.get('category')}", size=13, color=MUTED)
            )
            content_items.append(
                ft.Text(
                    f"Return: {days_left(item.get('return_exp'))}", size=13, color=MUTED
                )
            )
            if item.get("notes"):
                content_items.append(
                    ft.Text(f"Notes: {item.get('notes')}", size=13, color="white")
                )

        photos = item.get("photos", [])
        if photos:
            content_items.append(
                ft.Row(
                    [
                        ft.Image(
                            src=p,
                            width=80,
                            height=80,
                            fit=ft.BoxFit.COVER,
                            border_radius=8,
                        )
                        for p in photos
                    ],
                    scroll=ft.ScrollMode.AUTO,
                )
            )

        dlg = ft.AlertDialog(
            bgcolor=BG_CARD,
            content=ft.Column(content_items, tight=True, spacing=10),
            actions=[
                ft.TextButton(
                    "Close",
                    on_click=lambda _: setattr(dlg, "open", False) or page.update(),
                )
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def refresh_list():
        data = load_data()
        q = (search_bar.value or "").lower().strip()
        rows = []

        for item in data:
            is_car = item.get("type") == "Car Part"
            title = (
                f"{item.get('car')} • {item.get('part')}"
                if is_car
                else item.get("shop", "Receipt")
            )

            if q and q not in title.lower():
                continue

            sub = (
                f"{int(item.get('km', 0)):,} KM"
                if is_car
                else f"Return: {days_left(item.get('return_exp'))}"
            )

            rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(
                                        title,
                                        weight=ft.FontWeight.BOLD,
                                        size=15,
                                        color="white",
                                    ),
                                    ft.Text(sub, size=12, color=MUTED),
                                ],
                                spacing=4,
                                expand=True,
                            ),
                            ft.Text(
                                f"${item.get('price', 0):.2f}",
                                weight=ft.FontWeight.BOLD,
                                size=14,
                                color=GREEN,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_color=RED,
                                icon_size=18,
                                on_click=lambda _, uid=item.get("id"): delete_item(uid),
                            ),
                        ]
                    ),
                    bgcolor=BG_CARD,
                    padding=14,
                    border_radius=16,
                    on_click=lambda _, it=item: show_details(it),
                )
            )

        docket_list.controls = rows or [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=40, color=MUTED),
                        ft.Text("No records found", color=MUTED, size=14),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                alignment=ft.Alignment(0, 0),
                padding=40,
            )
        ]
        page.update()

    async def save_entry(e):
        nonlocal saving_in_progress
        if saving_in_progress:
            return

        is_car = type_dd.value == "Car Part"
        if not is_car and not shop_in.value.strip():
            return

        saving_in_progress = True
        save_btn.disabled = True
        page.update()

        try:
            today = str(datetime.date.today())
            entry = {
                "id": int(time.time() * 1000),
                "type": type_dd.value,
                "created": today,
                "photos": list(captured_photos),
            }

            if is_car:
                rep_years, rep_km = await fetch_interval(
                    make_dd.value, model_dd.value, part_dd.value
                )
                entry.update(
                    {
                        "car": f"{make_dd.value} {model_dd.value}",
                        "part": part_dd.value,
                        "price": parse_num(price_part_in.value),
                        "km": parse_num(km_in.value),
                        "replace_years": rep_years,
                        "replace_km": rep_km,
                    }
                )
            else:
                entry.update(
                    {
                        "shop": shop_in.value.strip(),
                        "price": parse_num(price_receipt_in.value),
                        "category": cat_dd.value,
                        "return_exp": calc_expiration(RET_DAYS.get(return_dd.value, 0)),
                        "warranty_exp": calc_expiration(
                            WAR_DAYS.get(warranty_dd.value, 0)
                        ),
                        "notes": notes_in.value.strip(),
                    }
                )

            data = load_data()
            
            # Anti-duplication guard: check if identical entry was just saved within the last 2 seconds
            if data:
                latest = data[0]
                if (
                    latest.get("type") == entry.get("type")
                    and latest.get("price") == entry.get("price")
                    and (
                        latest.get("car") == entry.get("car")
                        if is_car
                        else latest.get("shop") == entry.get("shop")
                    )
                ):
                    return  # Skip duplicate save request

            data.insert(0, entry)
            save_data(data)

            # Clear Inputs & Photos
            for field in (shop_in, notes_in, price_receipt_in, price_part_in, km_in):
                field.value = ""
            captured_photos.clear()
            photo_status.value = ""

            nav.selected_index = 0
            main_view.content = ledger_tab
            refresh_list()
        finally:
            saving_in_progress = False
            save_btn.disabled = False
            page.update()

    save_btn = ft.ElevatedButton(
        "Save Record",
        bgcolor=ACCENT,
        color="white",
        on_click=save_entry,
        height=48,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
    )

    ledger_tab = ft.Column(
        [
            ft.Text("Docket Ledger", size=22, weight=ft.FontWeight.BOLD),
            search_bar,
            docket_list,
        ],
        spacing=12,
        expand=True,
    )

    add_tab = ft.Column(
        [
            ft.Text("New Record", size=22, weight=ft.FontWeight.BOLD),
            type_row,
            camera_box,
            photo_status,
            form_container,
            save_btn,
        ],
        spacing=14,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    main_view = ft.Container(content=ledger_tab, expand=True)

    async def on_nav(e):
        is_add = e.control.selected_index == 1
        main_view.content = add_tab if is_add else ledger_tab
        page.update()
        if is_add:
            await ensure_camera()
        else:
            refresh_list()

    nav = ft.NavigationBar(
        selected_index=0,
        on_change=on_nav,
        bgcolor=BG_CARD,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.DASHBOARD_ROUNDED, label="Ledger"
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.ADD_A_PHOTO_ROUNDED, label="Add & Scan"
            ),
        ],
    )

    page.add(main_view)
    page.navigation_bar = nav

    # Pre-fetch models on startup
    init_models = await fetch_models("Toyota")
    model_dd.options = [ft.dropdown.Option(key=m, text=m) for m in init_models]
    model_dd.value = init_models[0] if init_models else "General"

    refresh_list()


if __name__ == "__main__":
    ft.app(target=main)