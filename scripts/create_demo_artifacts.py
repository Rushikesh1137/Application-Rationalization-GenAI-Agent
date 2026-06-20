from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.output_writer import CAPABILITY_LOSS_COLUMN, write_excel
from src.state import ECRState


INPUT_PATH = Path("sample_data/app_inventory_demo.xlsx")
OUTPUT_PATH = Path("sample_output/ecr_results_demo.xlsx")


def row(
    name: str,
    vendor: str,
    description: str,
    l1: str,
    l2: str,
    l3: str,
    function: str,
    recommendation: str,
    retained: str,
    rationale: str,
    capability_loss: str = "",
) -> dict[str, str]:
    return {
        "Name": name,
        "Vendor": vendor,
        "Description": description,
        "L1": l1,
        "L2": l2,
        "L3": l3,
        "Function": function,
        "Recommendation": recommendation,
        "App to be Retained": retained,
        "Rationale": rationale,
        CAPABILITY_LOSS_COLUMN: capability_loss,
    }


DEMO_ROWS = [
    row("Acme Integration Cloud", "AcmeSoft", "Strategic cloud integration platform for batch and API data movement.", "Technology", "Integration", "Data Integration", "Integration Platform", "Retain", "Acme Integration Cloud", "This is the strategic integration platform and covers both API and scheduled data movement."),
    row("Legacy Batch ETL", "AcmeSoft", "Deprecated batch ETL tool scheduled for retirement after migration to Acme Integration Cloud.", "Technology", "Integration", "Data Integration", "Batch ETL", "Eliminate", "Acme Integration Cloud", "This legacy ETL tool is superseded by Acme Integration Cloud for the same integration workflows."),
    row("FileMover v1", "Northstar", "Older managed file transfer instance used for regional nightly transfers.", "Technology", "Integration", "Data Integration", "Managed File Transfer", "Consolidate", "FileMover v2", "This is an older instance of the same managed file transfer product and should roll into FileMover v2."),
    row("FileMover v2", "Northstar", "Current managed file transfer platform for regional and enterprise nightly transfers.", "Technology", "Integration", "Data Integration", "Managed File Transfer", "Consolidate", "FileMover v2", "This is the retained anchor for the FileMover consolidation group."),
    row("API Gateway Admin", "Cloudway", "Administrative console for API gateway policies and developer onboarding.", "Technology", "Integration", "Data Integration", "API Management", "Retain", "API Gateway Admin", "This app provides a distinct API management capability with no duplicate in the cluster."),
    row("SourceSync QA", "AcmeSoft", "QA environment record for the SourceSync integration product.", "Technology", "Integration", "Data Integration", "Integration Testing", "Consolidate", "SourceSync", "This is an environment-specific record for the same SourceSync product."),
    row("SourceSync", "AcmeSoft", "Primary SourceSync product for source system data replication.", "Technology", "Integration", "Data Integration", "Integration Testing", "Consolidate", "SourceSync", "This is the retained anchor for the SourceSync product records."),
    row("AccessHub Cloud", "SecureID", "Modern cloud identity governance platform for access reviews and provisioning.", "Technology", "Security", "Identity Management", "Access Governance", "Retain", "AccessHub Cloud", "This is the strategic identity governance platform and remains the retained application."),
    row("AccessHub Classic", "SecureID", "Legacy on-prem access review tool being replaced by AccessHub Cloud.", "Technology", "Security", "Identity Management", "Access Governance", "Eliminate", "AccessHub Cloud", "This legacy access review tool is superseded by AccessHub Cloud for the same governance capability."),
    row("Password Vault", "VaultWorks", "Privileged password vault for infrastructure administrator accounts.", "Technology", "Security", "Identity Management", "Privileged Access", "Retain", "Password Vault", "This app provides privileged credential management and has no replacement in this cluster."),
    row("SSO Portal", "SecureID", "Single sign-on portal for workforce application access.", "Technology", "Security", "Identity Management", "Single Sign-On", "Consolidate", "SSO Portal", "This is the retained anchor for the SSO Portal environment records."),
    row("SSO Portal UAT", "SecureID", "UAT environment record for the same SSO Portal application.", "Technology", "Security", "Identity Management", "Single Sign-On", "Consolidate", "SSO Portal", "This is an environment-specific duplicate of the SSO Portal record."),
    row("Service Desk 360", "Helpwise", "Enterprise case and service request management platform for customer support.", "Operations", "Customer", "Customer Service", "Case Management", "Retain", "Service Desk 360", "This is the strategic case management platform for customer service workflows."),
    row("Legacy Case Portal", "Helpwise", "Older case intake portal transitioning to Service Desk 360.", "Operations", "Customer", "Customer Service", "Case Management", "Eliminate", "Service Desk 360", "This older portal is superseded by Service Desk 360 for customer case intake and tracking."),
    row("Chat Assist", "TalkNow", "Live chat assistant console for customer support agents.", "Operations", "Customer", "Customer Service", "Chat Support", "Retain", "Chat Assist", "This app supports live chat and remains distinct from case management."),
    row("Knowledge Base", "Helpwise", "Knowledge content portal for support articles and troubleshooting steps.", "Operations", "Customer", "Customer Service", "Knowledge Management", "Retain", "Knowledge Base", "This app provides knowledge management and no direct replacement is present."),
    row("Customer Survey Tool", "PulseCo", "Post-interaction survey collection and reporting for customer service.", "Operations", "Customer", "Customer Service", "Customer Feedback", "Retain", "Customer Survey Tool", "This app captures customer feedback and is not duplicated by the service desk platform."),
    row("PromoCloud", "MarketWorks", "Cloud campaign orchestration platform for email, SMS, and offer journeys.", "Commercial", "Marketing", "Marketing Automation", "Campaign Orchestration", "Retain", "PromoCloud", "This is the strategic marketing automation platform and should be retained."),
    row("PromoMail Classic", "MarketWorks", "Deprecated email campaign tool being phased out as journeys move to PromoCloud.", "Commercial", "Marketing", "Marketing Automation", "Campaign Orchestration", "Eliminate", "PromoCloud", "This legacy email tool is superseded by PromoCloud for campaign orchestration."),
    row("Email Studio East", "MarketWorks", "Regional deployment of Email Studio for eastern business units.", "Commercial", "Marketing", "Marketing Automation", "Email Campaigns", "Consolidate", "Email Studio", "This is a regional deployment record for the same Email Studio product."),
    row("Email Studio West", "MarketWorks", "Regional deployment of Email Studio for western business units.", "Commercial", "Marketing", "Marketing Automation", "Email Campaigns", "Consolidate", "Email Studio", "This is a regional deployment record for the same Email Studio product."),
    row("Email Studio", "MarketWorks", "Primary Email Studio record for campaign template management.", "Commercial", "Marketing", "Marketing Automation", "Email Campaigns", "Consolidate", "Email Studio", "This is the retained anchor for Email Studio regional records."),
    row("Audience Builder", "DataReach", "Audience segmentation workspace for marketing analysts.", "Commercial", "Marketing", "Marketing Automation", "Audience Segmentation", "Retain", "Audience Builder", "This app supports segmentation and has no clear replacement in this cluster."),
    row("Enterprise BI Platform", "InsightWare", "Strategic analytics platform for dashboards, semantic models, and governed reporting.", "Technology", "Data", "Reporting Analytics", "BI Platform", "Retain", "Enterprise BI Platform", "This is the strategic analytics platform and remains the retained application."),
    row("ReportMart Old", "InsightWare", "Legacy reporting portal scheduled for retirement as reports move to Enterprise BI Platform.", "Technology", "Data", "Reporting Analytics", "BI Platform", "Eliminate", "Enterprise BI Platform", "This legacy reporting portal is superseded by Enterprise BI Platform for governed reporting."),
    row("Finance Dashboard v1", "InsightWare", "Older finance dashboard record with the same metrics as Finance Dashboard v2.", "Technology", "Data", "Reporting Analytics", "Finance Reporting", "Consolidate", "Finance Dashboard v2", "This is an older dashboard record and should consolidate into Finance Dashboard v2."),
    row("Finance Dashboard v2", "InsightWare", "Current finance dashboard with the same metric scope and refreshed data model.", "Technology", "Data", "Reporting Analytics", "Finance Reporting", "Consolidate", "Finance Dashboard v2", "This is the retained anchor for the finance dashboard consolidation group."),
    row("Data Catalog", "MetaMap", "Catalog for data assets, owners, and definitions.", "Technology", "Data", "Reporting Analytics", "Data Catalog", "Retain", "Data Catalog", "This app provides metadata management and is not replaced by the BI platform."),
    row("SolidWorks Enterprise", "Dassault", "Strategic CAD platform for mechanical design collaboration and released part models.", "Product", "Engineering", "Engineering Design", "Mechanical CAD", "Retain", "SolidWorks Enterprise", "This is the strategic CAD platform and remains the retained engineering design system."),
    row("InventorPro Legacy", "Autodesk", "Legacy mechanical CAD tool used by a small team and being transitioned to SolidWorks Enterprise.", "Product", "Engineering", "Engineering Design", "Mechanical CAD", "Eliminate", "SolidWorks Enterprise", "This legacy CAD tool is being superseded by SolidWorks Enterprise for the same mechanical design capability."),
    row("CAD Viewer", "ViewCAD", "Read-only viewer for engineering models used by manufacturing teams.", "Product", "Engineering", "Engineering Design", "CAD Viewing", "Retain", "CAD Viewer", "This viewer supports downstream review and is not a duplicate of authoring CAD tools."),
    row("PDM Vault", "Dassault", "Product data management vault for released CAD files and engineering change records.", "Product", "Engineering", "Engineering Design", "Product Data Management", "Retain", "PDM Vault", "This app manages released design files and remains distinct from CAD authoring."),
    row("InvoiceFlow Cloud", "FinOps", "Cloud workflow for supplier invoice intake, matching, and approvals.", "Finance", "Procurement", "Accounts Payable", "Invoice Workflow", "Retain", "InvoiceFlow Cloud", "This is the strategic invoice workflow platform and should be retained."),
    row("InvoiceFlow On-Prem", "FinOps", "On-prem invoice workflow instance being migrated to InvoiceFlow Cloud.", "Finance", "Procurement", "Accounts Payable", "Invoice Workflow", "Eliminate", "InvoiceFlow Cloud", "This on-prem instance is superseded by InvoiceFlow Cloud for the same invoice workflow."),
    row("Supplier Portal", "SupplyNet", "Supplier self-service portal for onboarding and invoice status checks.", "Finance", "Procurement", "Accounts Payable", "Supplier Self-Service", "Retain", "Supplier Portal", "This app provides supplier self-service and is not duplicated by invoice workflow."),
    row("Payment Exceptions", "FinOps", "Tool for AP teams to review payment exceptions and holds.", "Finance", "Procurement", "Accounts Payable", "Payment Exception Review", "Consolidate", "Payment Exceptions", "This is the retained anchor for the Payment Exceptions duplicate record."),
    row("Payment Exceptions Copy", "FinOps", "Duplicate CMDB record for the Payment Exceptions tool.", "Finance", "Procurement", "Accounts Payable", "Payment Exception Review", "Consolidate", "Payment Exceptions", "This is a duplicate record for the same Payment Exceptions application."),
]


def build_states() -> list[ECRState]:
    states: list[ECRState] = []
    df = pd.DataFrame(DEMO_ROWS)
    for l3_name, group in df.groupby("L3", sort=False):
        apps = group[["Name", "Vendor", "Description", "L1", "L2", "L3"]].to_dict(orient="records")
        function_tags = {item["Name"]: item["Function"] for item in group.to_dict(orient="records")}
        decisions = []
        for item in group.to_dict(orient="records"):
            decisions.append(
                {
                    "App Name": item["Name"],
                    "Final L3": item["L3"],
                    "Function": item["Function"],
                    "Recommendation": item["Recommendation"],
                    "Rationale": item["Rationale"],
                    "App to be Retained": item["App to be Retained"],
                    CAPABILITY_LOSS_COLUMN: item[CAPABILITY_LOSS_COLUMN],
                }
            )
        states.append(
            {
                "l3_name": str(l3_name),
                "apps": apps,
                "max_retries": 5,
                "function_tags": function_tags,
                "failed_apps": [],
                "validator_feedback": {},
                "ecr_decisions": decisions,
                "capability_loss": {},
                "function_mismatch": None,
                "retry_count": 0,
                "status": "done",
            }
        )
    return states


def main() -> None:
    INPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    input_df = pd.DataFrame(DEMO_ROWS)[["Name", "Vendor", "Description", "L1", "L2", "L3"]]
    input_df.to_excel(INPUT_PATH, index=False)
    write_excel(build_states(), OUTPUT_PATH)
    print(f"Wrote demo input: {INPUT_PATH}")
    print(f"Wrote demo output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
