from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
import random
import string
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from alembic import command
from alembic.config import Config
import redis
from db import Link, URLRequest, URLResponse, URLStats
from datetime import datetime
from database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
import aioredis
from sqlalchemy.future import select
from auth.users import fastapi_users, auth_backend
from auth.schemas import UserRead, UserCreate  # Импортируй схемы Pydantic
from auth.db import User
from auth.users import current_active_user
import logging
from datetime import datetime, timedelta
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from tasks import celery_app

redis_client = aioredis.from_url("redis://localhost", decode_responses=True)

app = FastAPI()

def generate_short_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"]
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)

@app.get("/links/{short_code}")
async def get_original_url(short_code: str, db: AsyncSession = Depends(get_async_session)):
    cached_url = await redis_client.get(short_code)
    if cached_url:
        result = await db.execute(select(Link).where(Link.short_code == short_code))
        link_data = result.scalars().first()
        if link_data:
            link_data.visit_count = (link_data.visit_count or 0) + 1
            link_data.last_used_at = datetime.utcnow()
            await db.commit()
            await db.refresh(link_data)
        return {"original_url": cached_url}

    result = await db.execute(select(Link).filter(Link.short_code == short_code))
    link_data = result.scalars().first()
    if not link_data:
        raise HTTPException(status_code=404, detail="Link not found")

    link_data.visit_count = (link_data.visit_count or 0) + 1
    link_data.last_used_at = datetime.utcnow()
    await db.commit()
    await db.refresh(link_data)

    await redis_client.set(short_code, link_data.original_url) 
    return {"original_url": link_data.original_url}


logging.basicConfig(level=logging.INFO)


@app.delete("/links/{short_code}")
async def delete_short_url(short_code: str, db: AsyncSession = Depends(get_async_session), user: User = Depends(current_active_user)):
    logging.info(f"Trying to delete link: {short_code} by user: {user.id}")
    result = await db.execute(select(Link).where(Link.short_code == short_code))
    link_data = result.scalars().first()
    
    if not link_data:
        raise HTTPException(status_code=404, detail="Link not found")
    
    if link_data.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own links")
    
    await db.delete(link_data)
    await db.commit()
    
    await redis_client.delete(short_code)
    
    return {"message": "Link deleted successfully"}


@app.put("/links/{short_code}")
async def update_url(
    short_code: str,
    request: URLRequest,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    result = await db.execute(select(Link).where(Link.short_code == short_code))
    link_data = result.scalars().first()
    
    if not link_data:
        raise HTTPException(status_code=404, detail="Link not found")
    
    if link_data.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only update your own links")
    
    link_data.original_url = request.original_url
    await db.commit()
    
    await redis_client.set(short_code, request.original_url)
    
    return {"message": f"Link updated successfully to {request.original_url}"}


@app.get("/links/{short_code}")
async def get_original_url(short_code: str, db: AsyncSession = Depends(get_async_session)):
    cached_url = await redis_client.get(short_code)
    if cached_url:
        return {"original_url": cached_url}
    
    result = await db.execute(select(Link).where(Link.short_code == short_code))
    link_data = result.scalars().first()
    if not link_data:
        raise HTTPException(status_code=404, detail="Link not found")
    
    if link_data.expires_at and link_data.expires_at < datetime.utcnow():
        await db.delete(link_data)
        await db.commit()
        await redis_client.delete(short_code)  
        raise HTTPException(status_code=410, detail="Link has expired")  
    
    link_data.visit_count += 1
    link_data.last_used_at = datetime.utcnow()
    await db.commit()
    await redis_client.set(short_code, link_data.original_url)  
    return {"original_url": link_data.original_url}

@app.post("/links/shorten", response_model=URLResponse)
async def shorten_url(request: URLRequest, db: AsyncSession = Depends(get_async_session), user: User = Depends(current_active_user)):
    custom_alias = request.custom_alias if request.custom_alias else generate_short_code()

    existing_link = await db.execute(select(Link).filter(Link.short_code == custom_alias))
    existing_link = existing_link.scalars().first()

    if existing_link:
        raise HTTPException(status_code=400, detail="Alias already in use.")

    expires_at = None
    
    if request.expires_at:
        expires_at = datetime.strptime(request.expires_at, "%Y-%m-%dT%H:%M")
    
    user_id = user.id if user else None 
    
    new_link = Link(
        short_code=custom_alias,
        original_url=request.original_url,
        expires_at=expires_at,
        user_id=user_id 
    )
    
    db.add(new_link)
    await db.commit()
    await db.refresh(new_link)
    await redis_client.set(custom_alias, request.original_url)  
    return {"short_url": f"http://127.0.0.1:8000/links/{custom_alias}"}

@app.get("/links/search")
async def search_link(original_url: str = Query(...), db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(Link).where(Link.original_url == original_url))
    link_data = result.scalars().first()    
    if not link_data:
        raise HTTPException(status_code=404, detail="Link not found")
    
    return {"short_code": link_data.short_code, "original_url": link_data.original_url}

