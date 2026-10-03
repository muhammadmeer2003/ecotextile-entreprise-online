import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()
    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            if self._pageNumber > 1:
                self.saveState()
                self.setFont("Helvetica", 9)
                self.setFillColor(colors.HexColor("#4A5568"))
                self.drawString(54, 750, "EcoTextile Enterprises v3 -- Executive Operational Manual")
                self.setStrokeColor(colors.HexColor("#CBD5E1"))
                self.setLineWidth(0.5)
                self.line(54, 742, 558, 742)
                page_text = f"Page {self._pageNumber} of {num_pages}"
                self.drawRightString(558, 40, page_text)
                self.drawString(54, 40, "Confidential -- Corporate Operating System Document")
                self.line(54, 52, 558, 52)
                self.restoreState()
            super().showPage()
        super().save()

def build_pdf():
    # Force output directly into the local script directory to bypass Windows path drops
    current_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_path = os.path.join(current_dir, "EcoTextile_Enterprises_v3_User_Manual.pdf")
    
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=54, rightMargin=54, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    
    title_s = ParagraphStyle('T', fontName='Helvetica-Bold', fontSize=26, leading=32, textColor=colors.HexColor("#1E3A8A"), alignment=1)
    sub_s = ParagraphStyle('S', fontName='Helvetica', fontSize=14, leading=20, textColor=colors.HexColor("#0D9488"), alignment=1)
    meta_s = ParagraphStyle('M', fontName='Helvetica-Bold', fontSize=12, leading=18, textColor=colors.HexColor("#1F2937"), alignment=1)
    h1_s = ParagraphStyle('H1', fontName='Helvetica-Bold', fontSize=16, leading=22, textColor=colors.HexColor("#1E3A8A"), spaceBefore=14, spaceAfter=8, keepWithNext=True)
    h2_s = ParagraphStyle('H2', fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor("#0D9488"), spaceBefore=10, spaceAfter=4, keepWithNext=True)
    body_s = ParagraphStyle('B', fontName='Helvetica', fontSize=10, leading=15, textColor=colors.HexColor("#334155"), spaceAfter=6)
    code_s = ParagraphStyle('C', fontName='Courier', fontSize=9, leading=12, textColor=colors.HexColor("#0F172A"), backgroundColor=colors.HexColor("#F8FAFC"), borderPadding=6, spaceAfter=6)
    
    story = []
    story.append(Spacer(1, 120))
    story.append(Paragraph("ECOTEXTILE ENTERPRISES", title_s))
    story.append(Spacer(1, 10))
    story.append(Paragraph("EXECUTIVE OPERATIONAL MANUAL -- VERSION 3", ParagraphStyle('V', fontName='Helvetica-Bold', fontSize=13, alignment=1)))
    story.append(Paragraph("Partner Mills Operating System", sub_s))
    story.append(Spacer(1, 30))
    story.append(Paragraph("Production * Traceability * Warehouse * Quality * Sustainability * Control", ParagraphStyle('G', fontName='Helvetica-Oblique', fontSize=10, alignment=1, textColor=colors.HexColor("#4B5563"))))
    story.append(Spacer(1, 160))
    story.append(Paragraph("Prepared for Software Review, Demonstration & Operational Training", ParagraphStyle('P', fontName='Helvetica', fontSize=10, alignment=1, textColor=colors.HexColor("#4B5563"))))
    story.append(Spacer(1, 20))
    story.append(Paragraph("Lead Architect & Director:<br/><font size=14 color='#1E3A8A'>Muhammad MEER</font>", meta_s))
    story.append(PageBreak())
    
    story.append(Paragraph("1. DOCUMENT CONTROL", h1_s))
    data = [
        [Paragraph("<b>Attribute</b>", body_s), Paragraph("<b>Details</b>", body_s)],
        [Paragraph("Software Name", body_s), Paragraph("EcoTextile Enterprises", body_s)],
        [Paragraph("Version", body_s), Paragraph("v3 (Production Ready Local State)", body_s)],
        [Paragraph("Application Type", body_s), Paragraph("Textile Mill / Partner Mills Operating System", body_s)],
        [Paragraph("Technology Stack", body_s), Paragraph("Python, Flask, HTML5, CSS3, JavaScript, ReportLab, OpenPyXL", body_s)],
        [Paragraph("Database Engine", body_s), Paragraph("SQLite (Raw connection strings via models.py)", body_s)],
        [Paragraph("Primary Director", body_s), Paragraph("Muhammad MEER", body_s)]
    ]
    t = Table(data, colWidths=[150, 350])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (1,0), colors.HexColor("#F1F5F9")), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")), ('PADDING', (0,0), (-1,-1), 5)]))
    story.append(t)
    
    story.append(Paragraph("2. SYSTEM & TECHNOLOGY COHESION", h1_s))
    story.append(Paragraph("The EcoTextile Enterprises v3 platform links complex textile manufacturing workflows into a secure operational database layout. By utilizing raw <code>sqlite3</code> connection configurations optimized with Write-Ahead Logging (<code>journal_mode = WAL</code>) and an explicit 5000ms busy threshold, the application ensures synchronous ledger records without thread collision risks during heavy operational updates.", body_s))
    story.append(Paragraph("Static asset tracking maps storage targets directly to localized workstation physical pathways, explicitly structured inside <code>app.py</code> configuration matrices under <code>static/uploads/logos/</code> and <code>static/uploads/fabrics/</code>.", body_s))
    
    story.append(Paragraph("3. SYSTEM BLUEPRINT & ARCHITECTURE LIST (20 MODULES)", h1_s))
    story.append(Paragraph("The project implements a high-performance database tier built around an **Operational Event Logger** model. While Module 1 captures extensive batch-specific identity schemas, Modules 2 through 20 operate as real-time, lightweight transaction recorders that register logs instantly with automated time-stamps.", body_s))
    
    mods = [
        ("Module 1", "Production & Batch Control", "Core structured batch creation form tracking Buyer names, Fabric specifications, values, and image streams. Automatically computes unique Digital Product Passports (DPP)."),
        ("Module 2", "Procurement & Suppliers", "Records incoming raw cotton/fiber shipments and chemical inventory parameters from external suppliers."),
        ("Module 3", "Bill of Materials (BOM)", "Logs structural ingredient recipes, blend percentages, and baseline costing variables."),
        ("Module 4", "Cutting & Planning", "Tracks raw yard marker efficiency parameters and physical cutting room floor scrap weight totals."),
        ("Module 5", "Dyeing & Processing", "Logs wet processing heat metrics, formulation cycles, and structural pH levels."),
        ("Module 6", "Finishing & Treatment", "Records chemical coatings, stenter configurations, and canvas processing tracking data."),
        ("Module 7", "Quality Control (QC)", "Registers visual inspection metrics, defect points, and fabric durability tracking grades."),
        ("Module 8", "Production Planning", "Manages machine loom allocation timelines and weaving room shifts configurations."),
        ("Module 9", "Maintenance & OEE", "Tracks plant mechanical downtime data logs and components calibration intervals."),
        ("Module 10", "Warehouse & Rack Mapping", "Maps 3D storage placement metadata fields (Zone / Row / Rack identifiers)."),
        ("Module 11", "Inventory & Stock", "Monitors absolute counts of raw storage boxes and ready fabric rolls matrices."),
        ("Module 12", "Sales & Order Desk", "Maintains client deal confirmations and contract allocation parameters."),
        ("Module 13", "CBAM & Carbon Telemetry", "Records mill power indices and carbon coefficients per operational shifts."),
        ("Module 14", "Sustainability & DPP", "Compiles compliance validation records for complete product passport visibility."),
        ("Module 15", "Compliance & Audit", "Archives official certificate hashes and regulatory inspections markers."),
        ("Module 16", "Finance & Costing", "Tracks operational payroll matrix items and immediate utility bills metrics."),
        ("Module 17", "HR & Workforce", "Saves personnel shift rosters and tracking data for safety guidelines training."),
        ("Module 18", "Dispatch & Logistics", "Logs shipping manifest numbers, container codes, and cargo tracking references."),
        ("Module 19", "Customer Service", "Gathers post-shipment client validation metrics and buyer satisfaction feedback."),
        ("Module 20", "Executive Control Tower", "Aggregates macro KPIs from all tracking layers for instant leadership visibility.")
    ]
    for m_id, m_name, m_desc in mods:
        story.append(Paragraph(f"<b>{m_id}: {m_name}</b>", h2_s))
        story.append(Paragraph(f"{m_desc}", body_s))
        story.append(Spacer(1, 2))
        
    story.append(PageBreak())
    story.append(Paragraph("4. TRACEABILITY & EMISSIONS CORE MECHANICAL REASONING", h1_s))
    story.append(Paragraph("<b>Digital Product Passport (DPP) Functionality:</b> Token allocation is handled programmatically during Module 1 form compilation. The tracking routine binds a unique tracking token row to the batch data inside the database. When searched via the dashboard, the backend performs a localized index scan, instantly loading all production parameters onto the screen canvas.", body_s))
