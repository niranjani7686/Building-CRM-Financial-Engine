from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import Database
from app.routes import proposal_routes, quotation_routes, invoice_routes, payment_routes, analytics_routes, project_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Establish connection to MongoDB
    await Database.connect_db()
    yield
    # Shutdown: Close connection to MongoDB
    await Database.close_db()

app = FastAPI(
    title="Portal 5 - Finance & Client Management API",
    description="Backend services for Proposals, Quotations, Invoices, Payments, and Analytics.",
    version="1.0.0",
    lifespan=lifespan
)

# Register routers
app.include_router(proposal_routes.router, prefix="/api/proposals", tags=["Proposals"])
app.include_router(quotation_routes.router, prefix="/api/quotations", tags=["Quotations"])
app.include_router(invoice_routes.router, prefix="/api/invoices", tags=["Invoices"])
app.include_router(payment_routes.router, prefix="/api/payments", tags=["Payments"])
app.include_router(analytics_routes.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(project_routes.router, prefix="/api/projects", tags=["Client Projects"])

@app.get("/health", tags=["Health"])
async def health_check():
    """Service health check endpoint."""
    return {"status": "healthy", "service": "Portal 5 Finance & Client Management"}
