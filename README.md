# <img src="tonyengineering.png" alt="Tony Engineering" width="40" height="40"> DevOps Best Practices Impact Report

Measuring the impact of **DevOps best practices** implementation for a client. **Feature environments** setup followed by **continuous deployment** to production (**Auto-Deploy**) on **12 December 2023** were a **game changer** in the Software Development Lifecycle.

This also showcases the importance of a strong **automated testing culture** and constant **costs management optimization**.

This transformation was conducted following **[12-Factor App methodology](https://12factor.net/)** and **[Expand/Contract patterns](https://www.prisma.io/dataguide/types/relational/expand-and-contract-pattern#what-is-the-expand-and-contract-pattern)** to minimize incidents (**uptime > 99%** for the period 2022-2025).

## The Dashboard

# ➡️ **[VIEW LIVE DASHBOARD](https://tony-engineering-ou.github.io/devops-impact-report/autodeploy_impact_dashboard.html)** ⚡

📅 **[Schedule a consultation](https://calendly.com/tony-engineering/prise-connaissance)** - Let's discuss your DevOps and DataOps transformation

- **Deployment Success Rates**: Before vs After Auto-Deploy comparison
- **Deployment Speed Metrics**: Time reduction analysis
- **Test Coverage Trends**: Unit test coverage and E2E test growth
- **Infrastructure Costs**: AWS EC2 costs for feature environments
- **Feature Environment Usage**: Creation patterns over time
- **Data Pipeline Reliability**: Failure rate improvements

## How to Re-generate the Dashboard

> **Note**: This repository doesn't include the raw `.csv` data files for security reasons. You'll need to provide your own data files in the expected format.

### Prerequisites

- Python 3.8 or higher
- Git

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd devops-impact-report
   ```

2. **Create and activate virtual environment**
   ```bash
   # Create virtual environment
   python3 -m venv .venv
   
   # Activate virtual environment
   source .venv/bin/activate
   ```

3. **Install required packages**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Or install manually:
   pip install pandas
   ```

4. **Prepare your data files** (Required CSV files)
   
   The script expects the following data files in the project root:
   - `deploy_prod_pipelines_2022_2025_argocd_refined.csv` - Deployment pipeline data
   - `coverage_data_unit_tests.csv` - Unit test coverage data
   - `coverage_e2e_tests_count.csv` - E2E test count data
   - `ec2_costs_us_east_1.csv` - AWS EC2 cost data
   - `feature_environments_created_count.csv` - Feature environment creation data
   - `pipeline_success_failure_correlation.csv` - Pipeline correlation data
   - `data_pipeline_correlation_metrics_filtered.json` - Pipeline metrics JSON

5. **Generate the dashboard**
   ```bash
   python3 create_devops_impact_report.py
   ```

6. **View the dashboard**
   
   Open `autodeploy_impact_dashboard.html` in your browser to view the interactive dashboard.

## Author

**Antoine ROUGEOT** (Tony Engineering OÜ)  
LinkedIn: [antoinerougeot](https://www.linkedin.com/in/antoinerougeot/)
