    emp = await get_employee_by_telegram_id(telegram_id, db)

    item = (
        await db.execute(
            select(ChecklistItem).where(
                ChecklistItem.id == item_id, ChecklistItem.checklist_id == checklist_id
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Пункт не найден")

    # Validate content type — same rule as the web panel endpoint.
    # The bot always sends Telegram-downloaded files, but we enforce the check
    # here so a misconfigured or malicious bot process can't store arbitrary files.
    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    content_type = file.content_type or ""
    if not content_type.startswith("image/") or content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый тип файла «{content_type}». Разрешены: JPEG, PNG, WebP, GIF.",
        )

    content = await file.read()
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл слишком большой (max 8 MB)")

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    (Path(CHECKLIST_UPLOAD_DIR) / filename).write_bytes(content)

    photo = Photo(
        checklist_item_id=item.id,
        uploaded_by_employee_id=emp.id,
        url=f"/api/v1/checklists/photos/{filename}",
    )
    db.add(photo)
    await db.flush()

    await log_action(
        db, actor_id=emp.id, action="photo.uploaded", entity_type="checklist_item", entity_id=item.id,
        metadata={"photo_id": photo.id, "via": "telegram"},
    )

    await db.commit()
    await db.refresh(item)
    return await _build_item_out(item, db)