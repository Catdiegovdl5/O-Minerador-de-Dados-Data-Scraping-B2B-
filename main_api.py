from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import os
import pandas as pd
from prisma import Prisma

app = FastAPI()
db = Prisma()

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory logs for demonstration
logs = []

async def run_command(args):
    global logs
    process = await asyncio.create_subprocess_exec(
        "python3", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        text = line.decode().strip()
        logs.append(text)
        print(text)
    await process.wait()

async def run_full_engine(niche, city):
    # 1. Mining
    logs.append(f"--- STARTING MINING: {niche} in {city} ---")
    await run_command(["minerador_b2b.py", niche, city])

    # 2. Asset Generation
    logs.append("--- GENERATING SALES ASSETS (Dossiers/Screenshots) ---")
    await run_command(["prospector_vendas.py"])

    # 3. Automated Outreach
    logs.append("--- STARTING AUTOMATED OUTREACH ---")
    await run_command(["autofollow_prospect.py"])

    logs.append("--- FULL SALES ENGINE COMPLETED ---")

    # Sync leads to DB after pipeline finishes
    if not os.path.exists("Mineracao_B2B_TURBO.xlsx"):
        print("Excel file not found, skipping DB sync.")
        return

    try:
        df = pd.read_excel("Mineracao_B2B_TURBO.xlsx", sheet_name="Lista Completa")
        for _, row in df.iterrows():
            # Use phone + name as a unique identifier for idempotency
            phone = str(row.get('Phone', ''))
            name = str(row.get('Name', ''))

            existing = await db.lead.find_first(where={'phone': phone, 'name': name})

            data = {
                'name': name,
                'phone': phone,
                'website': str(row.get('Website', 'N/A')),
                'rating': float(row.get('Rating', 0.0)),
                'tem_pixel_meta': str(row.get('Tem_Pixel_Meta', 'Não')),
                'status': str(row.get('Status', ''))
            }

            if existing:
                await db.lead.update(where={'id': existing.id}, data=data)
            else:
                await db.lead.create(data=data)
        print(f"DB Sync Complete: {len(df)} records processed.")
    except Exception as e:
        print(f"DB Sync Error: {e}")

@app.get("/stats")
async def get_stats():
    try:
        df = pd.read_excel("Mineracao_B2B_TURBO.xlsx", sheet_name="Lista Completa")
        total = len(df)
        no_pixel = len(df[df['Tem_Pixel_Meta'] == "Não"])
        percent = (no_pixel / total * 100) if total > 0 else 0
        return {
            "total": total,
            "no_pixel_percent": round(percent, 1),
            "hot_leads": no_pixel
        }
    except:
        return {"total": 0, "no_pixel_percent": 0, "hot_leads": 0}

@app.get("/leads")
async def get_leads():
    try:
        leads = await db.lead.find_many(order={'createdAt': 'desc'})
        # Map DB fields to Frontend expected fields
        return [{
            "Name": l.name,
            "Phone": l.phone,
            "Website": l.website,
            "Rating": l.rating,
            "Tem_Pixel_Meta": l.tem_pixel_meta,
            "Status": l.status
        } for l in leads]
    except Exception as e:
        print(f"Fetch leads error: {e}")
        return []

@app.post("/mine")
async def start_mining(background_tasks: BackgroundTasks, niche: str = "Imobiliárias", city: str = "Londrina"):
    background_tasks.add_task(run_full_engine, niche, city)
    return {"message": f"Full Sales Engine for {niche} in {city} started in background"}

@app.get("/logs")
async def get_logs():
    return logs[-20:] # Return last 20 logs

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
