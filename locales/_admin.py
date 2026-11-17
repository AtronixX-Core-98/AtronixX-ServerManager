"""Admin panel texts: (Persian, English)."""

LINE = "━━━━━━━━━━━━━━━━"
HEAD = "👑 <b>%BRAND%</b> · پنل مدیریت\n" + LINE + "\n"
HEAD_EN = "👑 <b>%BRAND%</b> · Admin panel\n" + LINE + "\n"

ADMIN = {
    # ------------------------------------------------------------ buttons
    "b_users": ("👥 کاربران", "👥 Users"),
    "b_grant": ("🎟 اعطای اشتراک", "🎟 Grant a plan"),
    "b_stats": ("📊 آمار", "📊 Stats"),
    "b_mode": ("🔀 حالت ربات", "🔀 Bot mode"),
    "b_broadcast": ("📢 پیام همگانی", "📢 Broadcast"),
    "b_channels": ("📡 کانال‌های اجباری", "📡 Forced channels"),
    "b_backup": ("💾 بکاپ و ریستور", "💾 Backup & restore"),
    "b_sessions": ("🖥 نشست‌های زنده", "🖥 Live sessions"),
    "b_settings": ("⚙️ تنظیمات", "⚙️ Settings"),
    "b_adm_log": ("📜 گزارش فعالیت", "📜 Activity log"),
    "b_find": ("🔎 جستجو با آیدی", "🔎 Find by ID"),
    "b_revoke": ("❌ لغو اشتراک", "❌ Revoke plan"),
    "b_ban": ("🚫 مسدود کردن", "🚫 Ban"),
    "b_unban": ("✅ رفع مسدودی", "✅ Unban"),
    "b_delete_user": ("🗑 حذف کاربر", "🗑 Delete user"),
    "b_message": ("✉️ پیام", "✉️ Message"),
    "b_user_page": ("👤 صفحه‌ی کاربر", "👤 User page"),
    "b_to_free": ("🟢 رفتن به حالت عمومی", "🟢 Switch to public mode"),
    "b_to_paid": ("💎 رفتن به حالت اشتراکی", "💎 Switch to subscription mode"),
    "b_send_now": ("🚀 ارسال برای {n} نفر", "🚀 Send to {n} users"),
    "b_add_channel": ("➕ افزودن کانال", "➕ Add channel"),
    "b_backup_now": ("💾 بکاپ همین حالا", "💾 Back up now"),
    "b_restore": ("♻️ ریستور", "♻️ Restore"),
    "b_restore_now": ("♻️ بله، ریستور کن", "♻️ Yes, restore"),
    "f_all": ("همه", "All"),
    "f_sub": ("💎 اشتراکی", "💎 Subscribed"),
    "f_exp": ("⌛ منقضی", "⌛ Expired"),
    "f_banned": ("🚫 مسدود", "🚫 Banned"),
    "aud_all": ("👥 همه‌ی کاربران", "👥 All users"),
    "aud_subs": ("💎 فقط اشتراکی‌ها", "💎 Subscribers only"),
    "notified_yes": ("✅ پیام فعال‌سازی برای کاربر فرستاده شد", "✅ the activation message was sent to the user"),
    "notified_later": ("⏳ کاربر هنوز ربات رو استارت نزده؛ با اولین ورودش پیام فعال‌سازی براش می‌ره", "⏳ the user hasn't started the bot yet; the activation message is sent on their first visit"),
    # ------------------------------------------------------------ home and stats
    "adm_home": (
        HEAD + "🔀 حالت: <b>{mode}</b>\n👥 کاربران: <b>{users}</b>\n💎 اشتراک فعال: <b>{subs}</b>\n🚫 مسدود: <b>{banned}</b>\n🖥 نشست زنده: <b>{live}</b> از <b>{max}</b>",
        HEAD_EN + "🔀 Mode: <b>{mode}</b>\n👥 Users: <b>{users}</b>\n💎 Active plans: <b>{subs}</b>\n🚫 Banned: <b>{banned}</b>\n🖥 Live sessions: <b>{live}</b> of <b>{max}</b>",
    ),
    "adm_stats": (
        HEAD + "📊 <b>آمار</b>\n\n🔀 حالت: <b>{mode}</b>\n👥 کاربران: <b>{users}</b>\n💎 اشتراک فعال: <b>{subs}</b>\n🚫 مسدود: <b>{banned}</b>\n🖥 سرورهای ذخیره‌شده: <b>{hosts}</b>\n⚡ نشست ترمینال: <b>{live}</b>\n📁 نشست فایل: <b>{sftp}</b>\n🧠 رم ربات: <b>{ram} MB</b>\n⏱ آپتایم: {uptime}",
        HEAD_EN + "📊 <b>Stats</b>\n\n🔀 Mode: <b>{mode}</b>\n👥 Users: <b>{users}</b>\n💎 Active plans: <b>{subs}</b>\n🚫 Banned: <b>{banned}</b>\n🖥 Saved servers: <b>{hosts}</b>\n⚡ Terminal sessions: <b>{live}</b>\n📁 File sessions: <b>{sftp}</b>\n🧠 Bot RAM: <b>{ram} MB</b>\n⏱ Uptime: {uptime}",
    ),
    "adm_cannot_self": ("👑 این کار روی ادمین ممکن نیست.", "👑 This can't be done to the admin."),
    "adm_new_user": ("🆕 <b>کاربر جدید</b>\n👤 {name} · {username}\n🆔 <code>{uid}</code>", "🆕 <b>New user</b>\n👤 {name} · {username}\n🆔 <code>{uid}</code>"),
    "adm_sub_expired": ("⌛ اشتراک <b>{name}</b> (<code>{uid}</code>) تموم شد.", "⌛ The plan of <b>{name}</b> (<code>{uid}</code>) has ended."),
    # ------------------------------------------------------------ users
    "adm_users_title": (
        HEAD + "👥 <b>کاربران</b> ({total})\n💎 اشتراکی · ⌛ منقضی · 🚫 مسدود · ⚪ بدون اشتراک",
        HEAD_EN + "👥 <b>Users</b> ({total})\n💎 subscribed · ⌛ expired · 🚫 banned · ⚪ none",
    ),
    "adm_user": (
        HEAD + "👤 <b>{name}</b> · {username}\n🆔 <code>{uid}</code>\n📅 عضویت: {joined}\n👁 آخرین بازدید: {seen}\n🖥 سرورها: <b>{hosts}</b>\n🎟 اشتراک: {sub}\n🚫 مسدود: {banned}\n⚡ نشست زنده: {live}\n🤖 ربات رو استارت کرده: {started}",
        HEAD_EN + "👤 <b>{name}</b> · {username}\n🆔 <code>{uid}</code>\n📅 Joined: {joined}\n👁 Last seen: {seen}\n🖥 Servers: <b>{hosts}</b>\n🎟 Plan: {sub}\n🚫 Banned: {banned}\n⚡ Live session: {live}\n🤖 Started the bot: {started}",
    ),
    "adm_user_missing": ("❓ کاربری با آیدی <code>{uid}</code> پیدا نشد.", "❓ No user with ID <code>{uid}</code>."),
    "sub_active": ("فعال تا <b>{until}</b> ({days} روز مونده) · سقف <b>{max}</b> سرور", "active until <b>{until}</b> ({days} days left) · limit <b>{max}</b> servers"),
    "sub_expired": ("منقضی شده ({until})", "expired ({until})"),
    "sub_none": ("ندارد", "none"),
    "adm_revoke_confirm": ("❌ اشتراک کاربر <code>{uid}</code> لغو بشه؟", "❌ Revoke the plan of <code>{uid}</code>?"),
    "adm_delete_confirm": ("🗑 کاربر <code>{uid}</code> با <b>همه‌ی</b> سرورها و داده‌هاش حذف بشه؟", "🗑 Delete user <code>{uid}</code> with <b>all</b> their servers and data?"),
    "adm_user_deleted": ("✅ کاربر <code>{uid}</code> حذف شد.", "✅ User <code>{uid}</code> deleted."),
    "adm_find_ask": ("🔎 <b>آیدی عددی</b> کاربر رو بفرست", "🔎 Send the user's <b>numeric ID</b>"),
    "adm_bad_id": ("❗ آیدی عددی معتبر نیست.", "❗ Invalid numeric ID."),
    "adm_bad_number": ("❗ عدد معتبر نیست.", "❗ Invalid number."),
    "adm_msg_ask": ("✉️ متن پیام برای کاربر <code>{uid}</code> رو بفرست", "✉️ Send the message for user <code>{uid}</code>"),
    "adm_msg_sent": ("✅ پیام ارسال شد.", "✅ Message sent."),
    "adm_msg_failed": ("❌ ارسال نشد: {err}", "❌ Not delivered: {err}"),
    # ------------------------------------------------------------ grant a plan
    "adm_grant_ask_id": (
        HEAD + "🎟 <b>اعطای اشتراک</b>\n\n🆔 <b>آیدی عددی</b> کاربر رو بفرست\n<i>کاربر می‌تونه با دستور /id آیدی خودش رو ببینه.</i>",
        HEAD_EN + "🎟 <b>Grant a plan</b>\n\n🆔 Send the user's <b>numeric ID</b>\n<i>Users can see their own ID with /id.</i>",
    ),
    "adm_grant_ask_days": (
        "🎟 کاربر <code>{uid}</code>\n\n⏳ <b>تعداد روز</b> اشتراک رو بفرست (۱ تا ۳۶۵۰)\n<i>اگه اشتراک فعال داره، روزها به باقی‌مونده اضافه می‌شه.</i>",
        "🎟 User <code>{uid}</code>\n\n⏳ Send the number of <b>days</b> (1–3650)\n<i>If they already have an active plan, the days are added to the remaining time.</i>",
    ),
    "adm_grant_ask_hosts": ("🎟 کاربر <code>{uid}</code> · <b>{days}</b> روز\n\n🗄 <b>تعداد سرور</b> مجاز رو بفرست (۱ تا ۱۰۰۰)", "🎟 User <code>{uid}</code> · <b>{days}</b> days\n\n🗄 Send the allowed <b>number of servers</b> (1–1000)"),
    "adm_granted": (
        "✅ <b>اشتراک اعمال شد</b>\n\n🆔 <code>{uid}</code>\n⏳ {days} روز · 🗄 {hosts} سرور\n📅 اعتبار تا: <b>{until}</b>\n\n{notified}",
        "✅ <b>Plan granted</b>\n\n🆔 <code>{uid}</code>\n⏳ {days} days · 🗄 {hosts} servers\n📅 Valid until: <b>{until}</b>\n\n{notified}",
    ),
    # ------------------------------------------------------------ mode
    "adm_mode": (
        HEAD + "🔀 <b>حالت ربات</b>\n\nحالت فعلی: <b>{mode}</b>\n\n{note}",
        HEAD_EN + "🔀 <b>Bot mode</b>\n\nCurrent mode: <b>{mode}</b>\n\n{note}",
    ),
    "adm_mode_note_paid": (
        "با رفتن به «حالت اشتراکی» فقط کاربرانی که اشتراک فعال دارن دسترسی خواهند داشت. بقیه قفل می‌شن (داده‌شون می‌مونه) و نشست‌هاشون بسته می‌شه.",
        "In “subscription mode” only users with an active plan keep access. Everyone else is locked (their data stays) and their sessions are closed.",
    ),
    "adm_mode_note_free": (
        "با رفتن به «حالت عمومی» همه‌ی کاربران (به‌جز مسدودها) بدون نیاز به اشتراک دسترسی دارن.",
        "In “public mode” every user (except banned ones) has access with no plan needed.",
    ),
    "adm_mode_changed": ("✅ حالت ربات شد: <b>{mode}</b>", "✅ Bot mode is now: <b>{mode}</b>"),
    # ------------------------------------------------------------ broadcast
    "adm_bc_audience": (HEAD + "📢 <b>پیام همگانی</b>\nگیرنده‌ها کی باشن؟", HEAD_EN + "📢 <b>Broadcast</b>\nWho should receive it?"),
    "adm_bc_ask": ("📢 متن پیام (یا یک عکس با کپشن) رو بفرست.\n<i>قالب‌بندی تلگرام (بولد، لینک و...) حفظ می‌شه.</i>", "📢 Send the message text (or a photo with a caption).\n<i>Telegram formatting (bold, links...) is preserved.</i>"),
    "adm_bc_bad_format": ("❗ این پیام قابل ارسال نیست: {err}", "❗ This message can't be sent: {err}"),
    "adm_bc_confirm": ("📢 پیش‌نمایش بالاست.\n👥 گیرنده‌ها: <b>{n}</b> ({aud})\n\nارسال بشه؟", "📢 The preview is above.\n👥 Recipients: <b>{n}</b> ({aud})\n\nSend it?"),
    "adm_bc_busy": ("⏳ یه ارسال همگانی در حال انجامه.", "⏳ A broadcast is already running."),
    "adm_bc_progress": ("📢 در حال ارسال... <b>{done}</b> از <b>{total}</b>", "📢 Sending... <b>{done}</b> of <b>{total}</b>"),
    "adm_bc_done": ("✅ <b>ارسال تموم شد</b>\n\n📬 موفق: <b>{sent}</b>\n🚫 ربات رو بلاک کرده: <b>{blocked}</b>\n❌ ناموفق: <b>{failed}</b>", "✅ <b>Broadcast finished</b>\n\n📬 Delivered: <b>{sent}</b>\n🚫 Blocked the bot: <b>{blocked}</b>\n❌ Failed: <b>{failed}</b>"),
    # ------------------------------------------------------------ forced channels
    "adm_channels": (HEAD + "📡 <b>کانال‌های جوین اجباری</b> ({n})\nروی هر کانال بزنی حذف می‌شه.", HEAD_EN + "📡 <b>Forced-join channels</b> ({n})\nTap a channel to remove it."),
    "adm_channels_empty": (HEAD + "📡 <b>جوین اجباری خاموشه</b>\nیک یا چند کانال اضافه کن تا کاربرها قبل از استفاده عضوش بشن.", HEAD_EN + "📡 <b>Forced join is off</b>\nAdd one or more channels that users must join first."),
    "adm_channel_ask": ("📡 آیدی کانال رو بفرست (مثل <code>@mychannel</code> یا آیدی عددی) یا یه پیام از اون کانال فوروارد کن.\n⚠️ ربات باید توی اون کانال <b>ادمین</b> باشه.", "📡 Send the channel (like <code>@mychannel</code> or its numeric ID) or forward a message from it.\n⚠️ The bot must be an <b>admin</b> of that channel."),
    "adm_channel_bad": ("❗ فرمت درست نیست.", "❗ Invalid format."),
    "adm_channel_not_admin": ("❗ ربات توی این کانال ادمین نیست.", "❗ The bot isn't an admin of that channel."),
    "adm_channel_error": ("❗ خطا: {err}", "❗ Error: {err}"),
    "adm_channel_added": ("✅ کانال اضافه شد.", "✅ Channel added."),
    # ------------------------------------------------------------ backup
    "adm_backup": (
        HEAD + "💾 <b>بکاپ و ریستور</b>\n\n🔐 فایل بکاپ رمزگذاری‌شده (AES-256) و شامل دیتابیس + کلید اصلیه.\n🕒 بکاپ خودکار: هر <b>{hours}</b> ساعت توی همین چت\n📅 آخرین بکاپ: {last}\n\n♻️ برای ریستور، فایل <code>.smbak</code> رو برای ربات بفرست.",
        HEAD_EN + "💾 <b>Backup & restore</b>\n\n🔐 Backup files are encrypted (AES-256) and contain the database + the master key.\n🕒 Automatic backup: every <b>{hours}</b> hours into this chat\n📅 Last backup: {last}\n\n♻️ To restore, send the <code>.smbak</code> file to the bot.",
    ),
    "adm_backup_caption": ("💾 <b>بکاپ %BRAND%</b>\n👥 {users} کاربر · 🖥 {hosts} سرور\n📅 {when}\n🔐 رمزگذاری‌شده", "💾 <b>%BRAND% backup</b>\n👥 {users} users · 🖥 {hosts} servers\n📅 {when}\n🔐 Encrypted"),
    "adm_backup_failed": ("❌ بکاپ ناموفق بود:\n<code>{err}</code>", "❌ Backup failed:\n<code>{err}</code>"),
    "adm_restore_ask": ("♻️ <b>ریستور</b>\n\n⚠️ با ریستور، <b>همه‌ی داده‌های فعلی</b> با محتوای بکاپ جایگزین می‌شن.\n📎 فایل <code>.smbak</code> رو بفرست (حداکثر ۲۰ مگابایت).", "♻️ <b>Restore</b>\n\n⚠️ Restoring <b>replaces all current data</b> with the backup content.\n📎 Send the <code>.smbak</code> file (max 20 MB)."),
    "adm_restore_toobig": ("❗ فایل از ۲۰ مگابایت بزرگ‌تره.", "❗ The file is larger than 20 MB."),
    "adm_restore_invalid": ("❗ این فایل یه بکاپ معتبر از این ربات نیست.", "❗ This is not a valid backup of this bot."),
    "adm_restore_pass": ("🔑 این بکاپ با رمز دیگه‌ای ساخته شده. <b>رمز بکاپ</b> رو بفرست (پیامت پاک می‌شه).", "🔑 This backup was made with a different password. Send the <b>backup password</b> (your message will be deleted)."),
    "adm_restore_wrong": ("❗ رمز اشتباهه یا فایل خراب شده.", "❗ Wrong password or corrupted file."),
    "adm_restore_confirm": ("♻️ <b>بکاپ معتبره</b>\n\n👥 کاربران: <b>{users}</b>\n🖥 سرورها: <b>{hosts}</b>\n📅 ساخته‌شده: {when}\n\n⚠️ داده‌های فعلی جایگزین می‌شن. ادامه بدم؟", "♻️ <b>Valid backup</b>\n\n👥 Users: <b>{users}</b>\n🖥 Servers: <b>{hosts}</b>\n📅 Created: {when}\n\n⚠️ The current data will be replaced. Continue?"),
    "adm_restore_working": ("⏳ در حال ریستور...", "⏳ Restoring..."),
    "adm_restore_failed": ("❌ ریستور ناموفق بود و وضعیت قبلی برگردونده شد:\n<code>{err}</code>", "❌ Restore failed and the previous state was kept:\n<code>{err}</code>"),
    "adm_restore_done": ("✅ <b>ریستور انجام شد.</b>\nهمه‌ی نشست‌ها بسته شدن و داده‌ها بازیابی شدن.", "✅ <b>Restore complete.</b>\nAll sessions were closed and the data was recovered."),
    # ------------------------------------------------------------ sessions, settings, log
    "adm_sessions": (HEAD + "🖥 <b>نشست‌های زنده</b>: {n} از {max}\nروی هر نشست بزنی بسته می‌شه.", HEAD_EN + "🖥 <b>Live sessions</b>: {n} of {max}\nTap a session to close it."),
    "adm_settings": (
        HEAD + "⚙️ <b>تنظیمات</b>\n\n🖥 سقف نشست زنده‌ی هم‌زمان: <b>{max}</b>\n⏳ بستن نشست بیکار: بعد از <b>{idle}</b> دقیقه\n⏱ حداکثر عمر هر نشست: <b>{life}</b> ساعت\n🔔 بررسی اعلان قطعی: هر <b>{watch}</b> دقیقه\n🏠 دسترسی به همین سرور: <b>{ha}</b>\n\n<i>سقف نشست‌ها رو با دکمه‌ها عوض کن. بقیه از فایل .env تنظیم می‌شن.</i>",
        HEAD_EN + "⚙️ <b>Settings</b>\n\n🖥 Max concurrent live sessions: <b>{max}</b>\n⏳ Idle session timeout: <b>{idle}</b> min\n⏱ Max session lifetime: <b>{life}</b> h\n🔔 Downtime check interval: <b>{watch}</b> min\n🏠 “This server” access: <b>{ha}</b>\n\n<i>Change the session cap with the buttons. Everything else lives in the .env file.</i>",
    ),
    "adm_log": (HEAD + "📜 <b>آخرین فعالیت‌های ادمین</b>", HEAD_EN + "📜 <b>Recent admin activity</b>"),
    "adm_log_empty": ("<i>هنوز چیزی ثبت نشده.</i>", "<i>Nothing logged yet.</i>"),
}
