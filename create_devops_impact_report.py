import pandas as pd
import json
from datetime import datetime
from cost_savings_calculator import DevOpsCostSavingsCalculator

def create_autodeploy_dashboard():
    """Create an interactive HTML dashboard showing auto-deploy impact"""
    
    print("Loading deployment pipeline data...")
    
    # Calculate cost savings
    calculator = DevOpsCostSavingsCalculator()
    cost_results = calculator.calculate_total_savings()
    
    # Read the refined data with ArgoCD fix logic applied
    df = pd.read_csv('deploy_prod_pipelines_2022_2025_argocd_refined.csv')
    
    # Read test coverage, e2e test data, EC2 costs, and feature environments data
    coverage_df = pd.read_csv('coverage_data_unit_tests.csv')
    e2e_df = pd.read_csv('coverage_e2e_tests_count.csv')
    ec2_df = pd.read_csv('ec2_costs_us_east_1.csv')
    feature_envs_df = pd.read_csv('feature_environments_created_count.csv')
    
    # Read data pipeline insights (filtered to exclude scheduled ingestions)
    pipeline_success_df = pd.read_csv('pipeline_success_failure_correlation.csv')
    with open('data_pipeline_correlation_metrics_filtered.json', 'r') as f:
        pipeline_metrics = json.load(f)
    
    # Convert dates with flexible parsing
    df['branch_creation_datetime'] = pd.to_datetime(df['branch_creation_datetime'], utc=True, format='mixed')
    
    # Define the auto-deploy enablement date
    autodeploy_date = pd.to_datetime('2023-12-12T14:13:04.057Z')
    
    # Split data into before and after periods
    before = df[df['branch_creation_datetime'] < autodeploy_date]
    after = df[df['branch_creation_datetime'] >= autodeploy_date]
    
    # Calculate completion rates (pipelines with end_datetime vs total)
    before_completed = len(before[before['deploy_prod_job_end_datetime'].notna()])
    before_total = len(before)
    before_completion_rate = (before_completed / before_total * 100) if before_total > 0 else 0
    
    after_completed = len(after[after['deploy_prod_job_end_datetime'].notna()])
    after_total = len(after)
    after_completion_rate = (after_completed / after_total * 100) if after_total > 0 else 0
    
    # Calculate average deployment times (only for completed deployments with >0 days)
    before_deployed = before[before['days_elapsed_branch_to_deploy'] > 0]
    after_deployed = after[after['days_elapsed_branch_to_deploy'] > 0]
    
    before_avg_days = before_deployed['days_elapsed_branch_to_deploy'].mean() if len(before_deployed) > 0 else 0
    after_avg_days = after_deployed['days_elapsed_branch_to_deploy'].mean() if len(after_deployed) > 0 else 0
    
    # Calculate monthly trends
    df_monthly = df.copy()
    df_monthly['year_month'] = df_monthly['branch_creation_datetime'].dt.to_period('M')
    
    monthly_stats = df_monthly.groupby('year_month').apply(lambda x: pd.Series({
        'total_pipelines': len(x),
        'completed_pipelines': len(x[x['deploy_prod_job_end_datetime'].notna()]),
        'completion_rate': len(x[x['deploy_prod_job_end_datetime'].notna()]) / len(x) * 100,
        'deployed_pipelines': len(x[x['days_elapsed_branch_to_deploy'] > 0]),
        'avg_deployment_days': x[x['days_elapsed_branch_to_deploy'] > 0]['days_elapsed_branch_to_deploy'].mean() if len(x[x['days_elapsed_branch_to_deploy'] > 0]) > 0 else 0,
        'p90_deployment_days': x[x['days_elapsed_branch_to_deploy'] > 0]['days_elapsed_branch_to_deploy'].quantile(0.9) if len(x[x['days_elapsed_branch_to_deploy'] > 0]) > 0 else 0,
        'median_deployment_days': x[x['days_elapsed_branch_to_deploy'] > 0]['days_elapsed_branch_to_deploy'].median() if len(x[x['days_elapsed_branch_to_deploy'] > 0]) > 0 else 0,
        'auto_percentage': (x['deploy_prod_job_trigger'] == 'auto').sum() / len(x) * 100
    })).reset_index()
    
    monthly_stats['month_str'] = monthly_stats['year_month'].astype(str)
    monthly_stats['is_after_autodeploy'] = monthly_stats['year_month'] >= pd.Period('2023-12')
    
    # Process test coverage and e2e test data
    coverage_df['commit_date'] = pd.to_datetime(coverage_df['commit_date'])
    coverage_df['year_month'] = coverage_df['commit_date'].dt.to_period('M')
    
    e2e_df['commit_date'] = pd.to_datetime(e2e_df['commit_date'])
    e2e_df['year_month'] = e2e_df['commit_date'].dt.to_period('M')
    
    # Process EC2 costs data
    ec2_df['commit_date'] = pd.to_datetime(ec2_df['commit_date'])
    ec2_df['year_month'] = ec2_df['commit_date'].dt.to_period('M')
    
    # Merge test data and EC2 costs with monthly stats
    coverage_monthly = coverage_df.groupby('year_month').agg({
        'code_coverage': 'last'  # Take the last value for each month
    }).reset_index()
    
    e2e_monthly = e2e_df.groupby('year_month').agg({
        'number_of_tests': 'last'  # Take the last value for each month
    }).reset_index()
    
    ec2_monthly = ec2_df.groupby('year_month').agg({
        'ec2_cost_usd': 'last'  # Take the last value for each month
    }).reset_index()
    
    # Extend pipeline data to align with deployment data timeline (starting from 2022-10)
    all_months = monthly_stats['year_month'].tolist()
    extended_pipeline_months = []
    extended_failure_rates = []
    
    # Get pipeline failure rates from the filtered JSON, extending to match deployment timeline
    pipeline_months_from_json = [pd.Period(month) for month in pipeline_metrics['monthly_data']['months']]
    pipeline_failure_rates_from_json = pipeline_metrics['monthly_data']['failure_rates']
    
    for month in all_months:
        extended_pipeline_months.append(str(month))
        if month in pipeline_months_from_json:
            # Month exists in pipeline data
            idx = pipeline_months_from_json.index(month)
            extended_failure_rates.append(pipeline_failure_rates_from_json[idx])
        else:
            # Month doesn't exist in pipeline data, fill with None (no data)
            extended_failure_rates.append(None)
    
    # Prepare data for JavaScript
    dashboard_data = {
        'metrics': {
            'before': {
                'total_pipelines': before_total,
                'completed_pipelines': before_completed,
                'completion_rate': round(before_completion_rate, 1),
                'deployed_pipelines': len(before_deployed),
                'avg_deployment_days': round(before_avg_days, 1),
                'avg_deployment_hours': round(before_avg_days * 24, 1)
            },
            'after': {
                'total_pipelines': after_total,
                'completed_pipelines': after_completed,
                'completion_rate': round(after_completion_rate, 1),
                'deployed_pipelines': len(after_deployed),
                'avg_deployment_days': round(after_avg_days, 1),
                'avg_deployment_hours': round(after_avg_days * 24, 1)
            }
        },
        'improvements': {
            'completion_rate_change': round(after_completion_rate - before_completion_rate, 1),
            'completion_rate_change_pct': round((after_completion_rate - before_completion_rate) / before_completion_rate * 100, 1) if before_completion_rate > 0 else 0,
            'completion_rate_multiplier': round(after_completion_rate / before_completion_rate, 1) if before_completion_rate > 0 else 0,
            'deployment_time_change_pct': round((before_avg_days - after_avg_days) / before_avg_days * 100, 1) if before_avg_days > 0 else 0,
            'deployment_time_change_hours': round((before_avg_days - after_avg_days) * 24, 1),
            'volume_increase_pct': round((len(after_deployed) - len(before_deployed)) / len(before_deployed) * 100, 0) if len(before_deployed) > 0 else 0
        },
        'monthly_data': {
            'months': monthly_stats['month_str'].tolist(),
            'completion_rates': monthly_stats['completion_rate'].round(1).tolist(),
            'avg_deployment_days': monthly_stats['avg_deployment_days'].round(1).fillna(0).tolist(),
            'p90_deployment_days': monthly_stats['p90_deployment_days'].round(1).fillna(0).tolist(),
            'median_deployment_days': monthly_stats['median_deployment_days'].round(1).fillna(0).tolist(),
            'total_pipelines': monthly_stats['total_pipelines'].tolist(),
            'auto_percentages': monthly_stats['auto_percentage'].round(1).tolist(),
            'is_after_autodeploy': monthly_stats['is_after_autodeploy'].tolist()
        },
        'test_data': {
            'coverage_months': coverage_monthly['year_month'].astype(str).tolist(),
            'coverage_percentages': coverage_monthly['code_coverage'].round(1).tolist(),
            'e2e_months': e2e_monthly['year_month'].astype(str).tolist(),
            'e2e_counts': e2e_monthly['number_of_tests'].tolist()
        },
        'ec2_data': {
            'months': ec2_monthly['year_month'].astype(str).tolist(),
            'costs': ec2_monthly['ec2_cost_usd'].round(2).tolist()
        },
        'feature_envs_data': {
            'months': feature_envs_df['month'].tolist(),
            'counts': feature_envs_df['count'].tolist(),
            'feature_envs_start': '2023-09'  # When feature environments started
        },
        'pipeline_data': {
            'months': extended_pipeline_months,
            'failure_rates': extended_failure_rates,
            'overall_metrics': {
                'total_events': pipeline_metrics['summary']['total_pipeline_events'],
                'total_failures': pipeline_metrics['summary']['total_failures'],
                'overall_failure_rate': pipeline_metrics['summary']['overall_failure_rate']
            }
        },
        'cost_savings_data': {
            'historical_actual_savings': float(cost_results['historical_actual_savings_2024_2025']),
            'avg_monthly_savings': float(cost_results['key_metrics']['avg_monthly_savings_current']),
            'total_time_saved_business_days': float(cost_results['total_time_saved_business_days'])
        },
        'autodeploy_date': '2023-12'
    }
    
    # Create the HTML dashboard
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Auto-Deploy Impact Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @page {{
            size: A4;
            margin: 2cm 1.5cm;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.4;
            color: #000;
            background: #fff;
            max-width: 1400px;
            margin: 0 auto;
            padding: 2cm;
        }}
        
        h1 {{
            font-size: 28pt;
            font-weight: bold;
            margin-bottom: 12pt;
            text-align: left;
            border-bottom: 3pt solid #000;
            padding-bottom: 12pt;
        }}
        
        h2 {{
            font-size: 16pt;
            font-weight: bold;
            margin-top: 24pt;
            margin-bottom: 12pt;
            text-transform: uppercase;
        }}
        
        h3 {{
            font-size: 13pt;
            font-weight: bold;
            margin-top: 16pt;
            margin-bottom: 8pt;
        }}
        
        p {{
            margin-bottom: 10pt;
        }}
        
        .header-subtitle {{
            font-size: 12pt;
            margin-bottom: 20pt;
            line-height: 1.6;
        }}
        
        .focus-box {{
            border: 2pt solid #000;
            padding: 16pt;
            margin: 20pt 0;
            background: #f9f9f9;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20pt;
            margin: 20pt 0;
        }}
        
        .metric-card {{
            border: 1pt solid #000;
            padding: 16pt;
            background: #fff;
        }}
        
        .metric-card h3 {{
            margin-top: 0;
            margin-bottom: 12pt;
            font-size: 12pt;
        }}
        
        .metric-value {{
            font-size: 32pt;
            font-weight: bold;
            text-align: center;
            margin: 12pt 0;
        }}
        
        .metric-label {{
            text-align: center;
            font-size: 10pt;
            color: #666;
        }}
        
        .before-after {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12pt;
        }}
        
        .before, .after {{
            border: 1pt solid #000;
            padding: 12pt;
            text-align: center;
        }}
        
        .before {{
            background: #f5f5f5;
        }}
        
        .after {{
            background: #fff;
        }}
        
        .chart-container {{
            margin: 24pt 0;
            page-break-inside: avoid;
        }}
        
        .chart-wrapper {{
            border: 1pt solid #000;
            padding: 16pt;
            background: #fff;
        }}
        
        .author-info {{
            border-top: 2pt solid #000;
            padding-top: 16pt;
            margin-top: 24pt;
            font-size: 10pt;
        }}
        
        .summary {{
            border: 2pt solid #000;
            padding: 20pt;
            margin: 24pt 0;
            background: #f9f9f9;
        }}
        
        .summary h2 {{
            margin-top: 0;
        }}
        
        /* Print-specific styles */
        @media print {{
            body {{
                margin: 0;
                padding: 0;
                max-width: none;
            }}
            
            * {{
                -webkit-print-color-adjust: exact !important;
                color-adjust: exact !important;
            }}
            
            .chart-container {{
                page-break-inside: avoid;
            }}
            
            h2 {{
                page-break-after: avoid;
            }}
        }}
    </style>
</head>
<body>
    <h1>DevOps Best Practices Impact Report</h1>
    <div class="header-subtitle">
        <p>Measuring the impact of DevOps best practices implementation showing both operational improvements and financial impact. Feature environments setup followed by continuous deployment to production (Auto-Deploy) on <strong>12 December 2023</strong> were a game changer in the Software Development Lifecycle.</p>
    </div>
    
    <div class="focus-box">
        <h3>Key Transformation</h3>
        <p>This transformation was conducted following <strong>12-Factor App methodology</strong> and <strong>Expand/Contract patterns</strong> to minimize incidents (uptime > 99% for period 2022-2025).</p>
    </div>

    <h2>Financial Impact</h2>
    <div class="metrics-grid">
        <div class="metric-card">
            <h3>Total Estimated Savings</h3>
            <div class="metric-value" id="total-savings">-</div>
            <div class="metric-label">For period 2024-2025</div>
        </div>
        
        <div class="metric-card">
            <h3>Time Saved</h3>
            <div class="metric-value" id="business-days-saved">-</div>
            <div class="metric-label">Business days saved for devs and data scientists</div>
        </div>
    </div>

    <h2>Operational Metrics</h2>
    <div class="metrics-grid">
        <div class="metric-card">
            <h3>Completion Rate</h3>
            <div class="before-after">
                <div class="before">
                    <div class="metric-label">Before Auto-Deploy</div>
                    <div class="metric-value" style="font-size: 24pt;" id="before-completion">-</div>
                    <div class="metric-label">Success Rate</div>
                </div>
                <div class="after">
                    <div class="metric-label">After Auto-Deploy</div>
                    <div class="metric-value" style="font-size: 24pt;" id="after-completion">-</div>
                    <div class="metric-label">Success Rate</div>
                </div>
            </div>
        </div>
        
        <div class="metric-card">
            <h3>Average Deployment Time</h3>
            <div class="before-after">
                <div class="before">
                    <div class="metric-label">Before Auto-Deploy</div>
                    <div class="metric-value" style="font-size: 24pt;" id="before-time">-</div>
                    <div class="metric-label">Days</div>
                </div>
                <div class="after">
                    <div class="metric-label">After Auto-Deploy</div>
                    <div class="metric-value" style="font-size: 24pt;" id="after-time">-</div>
                    <div class="metric-label">Days</div>
                </div>
            </div>
        </div>
        
        <div class="metric-card">
            <h3>Completion Rate Improvement</h3>
            <div class="metric-value" id="completion-improvement">-</div>
            <div class="metric-label">More Reliable</div>
        </div>
        
        <div class="metric-card">
            <h3>Speed Improvement</h3>
            <div class="metric-value" id="speed-improvement">-</div>
            <div class="metric-label">Faster Deployments</div>
        </div>
    </div>

    <h2>Detailed Analysis</h2>
    
    <div class="chart-container">
        <h3>Deployments Success Rates</h3>
        <div class="chart-wrapper">
            <canvas id="completionChart"></canvas>
        </div>
    </div>
    
    <div class="chart-container">
        <h3>Monthly Deployment Time Trend</h3>
        <div class="chart-wrapper">
            <canvas id="deploymentChart"></canvas>
        </div>
    </div>
    
    <div class="chart-container">
        <h3>Test Coverage & E2E Tests Trend</h3>
        <div class="chart-wrapper">
            <canvas id="testChart"></canvas>
        </div>
    </div>
    
    <div class="chart-container">
        <h3>AWS EC2 Costs for Feature Environments</h3>
        <div class="chart-wrapper">
            <canvas id="ec2Chart"></canvas>
        </div>
    </div>
    
    <div class="chart-container">
        <h3>Feature Environments Created Over Time</h3>
        <div class="chart-wrapper">
            <canvas id="featureEnvsChart"></canvas>
        </div>
    </div>
    
    <div class="chart-container">
        <h3>Data Pipeline Failures Over Time</h3>
        <div class="chart-wrapper">
            <canvas id="pipelineReliabilityChart"></canvas>
        </div>
    </div>

    <div class="summary">
        <h2>Key Takeaways</h2>
        <p>
            The auto-deploy enablement on <strong>December 12, 2023</strong> resulted in <strong>15.3x more reliable deployments</strong> and <strong>57.3% faster deployments</strong>. This transformation moved the team from manual, error-prone deployments to automated, reliable, and fast continuous deployment.
        </p>
        <p style="margin-top: 12pt;">
            The introduction of <strong>feature environments in September 2023</strong> was a mandatory step to move safely to continuous deployment, providing isolated testing environments that enabled confident automated deployments without production risks.
        </p>
        <p style="margin-top: 12pt;">
            Additionally, DevOps best practices adoption stabilized the data pipelines failure rate on production, reducing failures by approximately <strong>50-60%</strong> compared to pre-automation periods.
        </p>
    </div>

    <div class="author-info">
        <p><strong>Antoine ROUGEOT</strong> - Tony Engineering OÜ<br>
        Work available on GitHub: <a href="https://github.com/tony-engineering/devops-impact-report">github.com/tony-engineering/devops-impact-report</a><br>
        LinkedIn: <a href="https://www.linkedin.com/in/antoinerougeot/">linkedin.com/in/antoinerougeot</a></p>
    </div>
            <br>
            <p>
                Additionally, DevOps best practices adoption stabilized the data pipelines failure rate on production, 
                reducing failures by approximately <strong>50-60%</strong> compared to pre-automation periods.
            </p>
            <br>
            <p>
                Data gathered by scrapping APIs: CI/CD, Code Commits, Logs System, Code Coverage system. 
            </p>
            <p>
                Used Warp Terminal to generate the scrapping commands and generate HTML. No sensitive information are exposed in this report.
            </p>
        </div>
    </div>

    <script>
        // Data from Python
        const data = {json.dumps(dashboard_data, indent=12)};
        
        // Update metrics
        document.getElementById('before-completion').textContent = data.metrics.before.completion_rate + '%';
        document.getElementById('after-completion').textContent = data.metrics.after.completion_rate + '%';
        document.getElementById('before-time').textContent = data.metrics.before.avg_deployment_days;
        document.getElementById('after-time').textContent = data.metrics.after.avg_deployment_days;
        document.getElementById('completion-improvement').textContent = data.improvements.completion_rate_multiplier + 'x';
        document.getElementById('speed-improvement').textContent = data.improvements.deployment_time_change_pct + '%';
        
        // Update cost savings metric (clean formatting)
        const totalSavings = Math.round(data.cost_savings_data.historical_actual_savings);
        document.getElementById('total-savings').textContent = '$' + (totalSavings/1000).toFixed(0) + 'K';
        
        // Update business days saved
        const businessDaysSaved = Math.round(data.cost_savings_data.total_time_saved_business_days);
        document.getElementById('business-days-saved').textContent = businessDaysSaved.toLocaleString() + ' business days saved';
        
        
        // Find auto-deploy date index for vertical marker
        const autoDeployIndex = data.monthly_data.months.indexOf('2023-12');
        const testAutoDeployIndexCoverage = data.test_data.coverage_months.indexOf('2023-12');
        const testAutoDeployIndexE2e = data.test_data.e2e_months.indexOf('2023-12');
        const ec2AutoDeployIndex = data.ec2_data.months.indexOf('2023-12');
        const featureEnvsStartIndex = data.feature_envs_data.months.indexOf(data.feature_envs_data.feature_envs_start);
        const featureEnvsAutoDeployIndex = data.feature_envs_data.months.indexOf('2023-12');
        
        // Completion Rate Chart
        const completionCtx = document.getElementById('completionChart').getContext('2d');
        new Chart(completionCtx, {{
            type: 'line',
            data: {{
                labels: data.monthly_data.months,
                datasets: [{{
                    label: 'Completion Rate (%)',
                    data: data.monthly_data.completion_rates,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    tension: 0.4,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: true
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        title: {{
                            display: true,
                            text: 'Completion Rate (%)'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Month'
                        }}
                    }}
                }}
            }},
            plugins: [{{
                afterDraw: function(chart) {{
                    if (autoDeployIndex >= 0) {{
                        const ctx = chart.ctx;
                        const xAxis = chart.scales.x;
                        const yAxis = chart.scales.y;
                        const x = xAxis.getPixelForValue(autoDeployIndex);
                        
                        ctx.save();
                        ctx.strokeStyle = 'rgb(54, 162, 235)';
                        ctx.setLineDash([5, 5]);
                        ctx.lineWidth = 2;
                        ctx.beginPath();
                        ctx.moveTo(x, yAxis.top);
                        ctx.lineTo(x, yAxis.bottom);
                        ctx.stroke();
                        
                        // Add label
                        ctx.font = 'bold 12px Arial';
                        ctx.fillStyle = 'rgb(54, 162, 235)';
                        ctx.textAlign = 'center';
                        ctx.fillText('Auto-Deploy', x, yAxis.top + 20);
                        ctx.fillText('Enabled', x, yAxis.top + 35);
                        ctx.restore();
                    }}
                }}
            }}]
        }});
        
        // Deployment Time Chart - Average only for cleaner view
        const deploymentCtx = document.getElementById('deploymentChart').getContext('2d');
        new Chart(deploymentCtx, {{
            type: 'line',
            data: {{
                labels: data.monthly_data.months,
                datasets: [
                    {{
                        label: 'Average Deployment Time (days)',
                        data: data.monthly_data.avg_deployment_days,
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        tension: 0.4,
                        fill: true,
                        borderWidth: 3,
                        pointRadius: 4,
                        pointBackgroundColor: 'rgb(255, 99, 132)',
                        pointBorderColor: 'white',
                        pointBorderWidth: 2
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Days'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Month'
                        }}
                    }}
                }}
            }},
            plugins: [{{
                afterDraw: function(chart) {{
                    if (autoDeployIndex >= 0) {{
                        const ctx = chart.ctx;
                        const xAxis = chart.scales.x;
                        const yAxis = chart.scales.y;
                        const x = xAxis.getPixelForValue(autoDeployIndex);
                        
                        ctx.save();
                        ctx.strokeStyle = 'rgb(54, 162, 235)';
                        ctx.setLineDash([5, 5]);
                        ctx.lineWidth = 2;
                        ctx.beginPath();
                        ctx.moveTo(x, yAxis.top);
                        ctx.lineTo(x, yAxis.bottom);
                        ctx.stroke();
                        
                        // Add label
                        ctx.font = 'bold 12px Arial';
                        ctx.fillStyle = 'rgb(54, 162, 235)';
                        ctx.textAlign = 'center';
                        ctx.fillText('Auto-Deploy', x, yAxis.top + 20);
                        ctx.fillText('Enabled', x, yAxis.top + 35);
                        ctx.restore();
                    }}
                }}
            }}]
        }});
        
        // Test Coverage and E2E Tests Chart
        const testCtx = document.getElementById('testChart').getContext('2d');
        new Chart(testCtx, {{
            type: 'line',
            data: {{
                labels: data.test_data.coverage_months,  // Using coverage months as primary labels
                datasets: [
                    {{
                        label: 'Unit Test Coverage (%)',
                        data: data.test_data.coverage_percentages,
                        borderColor: 'rgb(54, 162, 235)',
                        backgroundColor: 'rgba(54, 162, 235, 0.2)',
                        tension: 0.4,
                        fill: false,
                        yAxisID: 'y',
                        borderWidth: 3,
                        pointRadius: 4,
                        pointBackgroundColor: 'rgb(54, 162, 235)',
                        pointBorderColor: 'white',
                        pointBorderWidth: 2
                    }},
                    {{
                        label: 'Web E2E Tests (#)',
                        data: data.test_data.e2e_counts,
                        borderColor: 'rgb(255, 159, 64)',
                        backgroundColor: 'rgba(255, 159, 64, 0.2)',
                        tension: 0.4,
                        fill: false,
                        yAxisID: 'y1',
                        borderWidth: 3,
                        pointRadius: 4,
                        pointBackgroundColor: 'rgb(255, 159, 64)',
                        pointBorderColor: 'white',
                        pointBorderWidth: 2
                    }}
                ]
            }},
            options: {{
                responsive: true,
                interaction: {{
                    mode: 'index',
                    intersect: false,
                }},
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }},
                scales: {{
                    x: {{
                        display: true,
                        title: {{
                            display: true,
                            text: 'Month'
                        }}
                    }},
                    y: {{
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {{
                            display: true,
                            text: 'Coverage (%)'
                        }},
                        min: 50,
                        max: 100
                    }},
                    y1: {{
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {{
                            display: true,
                            text: 'Number of E2E Tests'
                        }},
                        grid: {{
                            drawOnChartArea: false,
                        }},
                        min: 0
                    }}
                }}
            }},
            plugins: [{{
                afterDraw: function(chart) {{
                    if (testAutoDeployIndexCoverage >= 0) {{
                        const ctx = chart.ctx;
                        const xAxis = chart.scales.x;
                        const yAxis = chart.scales.y;
                        const x = xAxis.getPixelForValue(testAutoDeployIndexCoverage);
                        
                        ctx.save();
                        ctx.strokeStyle = 'rgb(54, 162, 235)';
                        ctx.setLineDash([5, 5]);
                        ctx.lineWidth = 2;
                        ctx.beginPath();
                        ctx.moveTo(x, yAxis.top);
                        ctx.lineTo(x, yAxis.bottom);
                        ctx.stroke();
                        
                        // Add label
                        ctx.font = 'bold 12px Arial';
                        ctx.fillStyle = 'rgb(54, 162, 235)';
                        ctx.textAlign = 'center';
                        ctx.fillText('Auto-Deploy', x, yAxis.top + 20);
                        ctx.fillText('Enabled', x, yAxis.top + 35);
                        ctx.restore();
                    }}
                }}
            }}]
        }});
        
        // EC2 Costs Chart
        const ec2Ctx = document.getElementById('ec2Chart').getContext('2d');
        new Chart(ec2Ctx, {{
            type: 'line',
            data: {{
                labels: data.ec2_data.months,
                datasets: [
                    {{
                        label: 'EC2 Costs (USD)',
                        data: data.ec2_data.costs,
                        borderColor: 'rgb(34, 197, 94)',
                        backgroundColor: 'rgba(34, 197, 94, 0.2)',
                        tension: 0.4,
                        fill: true,
                        borderWidth: 3,
                        pointRadius: 4,
                        pointBackgroundColor: 'rgb(34, 197, 94)',
                        pointBorderColor: 'white',
                        pointBorderWidth: 2
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Cost (USD)'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Month'
                        }}
                    }}
                }}
            }},
            plugins: [{{
                afterDraw: function(chart) {{
                    const ctx = chart.ctx;
                    const xAxis = chart.scales.x;
                    const yAxis = chart.scales.y;
                    
                    // Mark when feature environments were introduced (September 2023)
                    const ec2FeatureEnvsStartIndex = data.ec2_data.months.indexOf('2023-09');
                    if (ec2FeatureEnvsStartIndex >= 0) {{
                        const xStart = xAxis.getPixelForValue(ec2FeatureEnvsStartIndex);
                        
                        ctx.save();
                        ctx.strokeStyle = 'rgb(34, 197, 94)';
                        ctx.setLineDash([3, 3]);
                        ctx.lineWidth = 2;
                        ctx.beginPath();
                        ctx.moveTo(xStart, yAxis.top);
                        ctx.lineTo(xStart, yAxis.bottom);
                        ctx.stroke();
                        
                        // Add label
                        ctx.font = 'bold 12px Arial';
                        ctx.fillStyle = 'rgb(34, 197, 94)';
                        ctx.textAlign = 'center';
                        ctx.fillText('Feature Envs', xStart, yAxis.bottom - 75);
                        ctx.fillText('Introduced', xStart, yAxis.bottom - 60);
                        ctx.restore();
                    }}
                    
                    // Mark when auto-deploy was enabled
                    if (ec2AutoDeployIndex >= 0) {{
                        const ctx = chart.ctx;
                        const xAxis = chart.scales.x;
                        const yAxis = chart.scales.y;
                        const x = xAxis.getPixelForValue(ec2AutoDeployIndex);
                        
                        ctx.save();
                        ctx.strokeStyle = 'rgb(54, 162, 235)';
                        ctx.setLineDash([5, 5]);
                        ctx.lineWidth = 2;
                        ctx.beginPath();
                        ctx.moveTo(x, yAxis.top);
                        ctx.lineTo(x, yAxis.bottom);
                        ctx.stroke();
                        
                        // Add label
                        ctx.font = 'bold 12px Arial';
                        ctx.fillStyle = 'rgb(54, 162, 235)';
                        ctx.textAlign = 'center';
                        ctx.fillText('Auto-Deploy', x, yAxis.top + 20);
                        ctx.fillText('Enabled', x, yAxis.top + 35);
                        ctx.restore();
                    }}
                }}
            }}]
        }});
        
        // Feature Environments Created Chart
        const featureEnvsCtx = document.getElementById('featureEnvsChart').getContext('2d');
        new Chart(featureEnvsCtx, {{
            type: 'line',
            data: {{
                labels: data.feature_envs_data.months,
                datasets: [
                    {{
                        label: 'Feature Environments Created',
                        data: data.feature_envs_data.counts,
                        borderColor: 'rgb(147, 51, 234)',
                        backgroundColor: 'rgba(147, 51, 234, 0.2)',
                        tension: 0.4,
                        fill: true,
                        borderWidth: 3,
                        pointRadius: 4,
                        pointBackgroundColor: 'rgb(147, 51, 234)',
                        pointBorderColor: 'white',
                        pointBorderWidth: 2
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Environments Created'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Month'
                        }}
                    }}
                }}
            }},
            plugins: [{{
                afterDraw: function(chart) {{
                    const ctx = chart.ctx;
                    const xAxis = chart.scales.x;
                    const yAxis = chart.scales.y;
                    
                    // Mark when feature environments were introduced
                    if (featureEnvsStartIndex >= 0) {{
                        const xStart = xAxis.getPixelForValue(featureEnvsStartIndex);
                        
                        ctx.save();
                        ctx.strokeStyle = 'rgb(34, 197, 94)';
                        ctx.setLineDash([3, 3]);
                        ctx.lineWidth = 2;
                        ctx.beginPath();
                        ctx.moveTo(xStart, yAxis.top);
                        ctx.lineTo(xStart, yAxis.bottom);
                        ctx.stroke();
                        
                        // Add label
                        ctx.font = 'bold 12px Arial';
                        ctx.fillStyle = 'rgb(34, 197, 94)';
                        ctx.textAlign = 'center';
                        ctx.fillText('Feature Envs', xStart, yAxis.bottom - 30);
                        ctx.fillText('Introduced', xStart, yAxis.bottom - 15);
                        ctx.restore();
                    }}
                    
                    // Mark when auto-deploy was enabled
                    if (featureEnvsAutoDeployIndex >= 0) {{
                        const xAuto = xAxis.getPixelForValue(featureEnvsAutoDeployIndex);
                        
                        ctx.save();
                        ctx.strokeStyle = 'rgb(54, 162, 235)';
                        ctx.setLineDash([5, 5]);
                        ctx.lineWidth = 2;
                        ctx.beginPath();
                        ctx.moveTo(xAuto, yAxis.top);
                        ctx.lineTo(xAuto, yAxis.bottom);
                        ctx.stroke();
                        
                        // Add label
                        ctx.font = 'bold 12px Arial';
                        ctx.fillStyle = 'rgb(54, 162, 235)';
                        ctx.textAlign = 'center';
                        ctx.fillText('Auto-Deploy', xAuto, yAxis.top + 20);
                        ctx.fillText('Enabled', xAuto, yAxis.top + 35);
                        ctx.restore();
                    }}
                }}
            }}]
        }});
        
        // Data Pipeline Reliability Chart
        const pipelineReliabilityCtx = document.getElementById('pipelineReliabilityChart').getContext('2d');
        const pipelineAutoDeployIndex = data.pipeline_data.months.indexOf('2023-12');
        
        new Chart(pipelineReliabilityCtx, {{
            type: 'line',
            data: {{
                labels: data.pipeline_data.months,
                datasets: [
                    {{
                        label: 'Failure Rate (%)',
                        data: data.pipeline_data.failure_rates,
                        borderColor: 'rgb(239, 68, 68)',
                        backgroundColor: 'rgba(239, 68, 68, 0.2)',
                        tension: 0.4,
                        fill: true,
                        borderWidth: 3,
                        pointRadius: 4,
                        pointBackgroundColor: 'rgb(239, 68, 68)',
                        pointBorderColor: 'white',
                        pointBorderWidth: 2
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: true,
                        position: 'top'
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 20,
                        title: {{
                            display: true,
                            text: 'Failure Rate (%)'
                        }}
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: 'Month'
                        }}
                    }}
                }}
            }},
            plugins: [{{
                afterDraw: function(chart) {{
                    if (pipelineAutoDeployIndex >= 0) {{
                        const ctx = chart.ctx;
                        const xAxis = chart.scales.x;
                        const yAxis = chart.scales.y;
                        const x = xAxis.getPixelForValue(pipelineAutoDeployIndex);
                        
                        ctx.save();
                        ctx.strokeStyle = 'rgb(54, 162, 235)';
                        ctx.setLineDash([5, 5]);
                        ctx.lineWidth = 2;
                        ctx.beginPath();
                        ctx.moveTo(x, yAxis.top);
                        ctx.lineTo(x, yAxis.bottom);
                        ctx.stroke();
                        
                        // Add label
                        ctx.font = 'bold 12px Arial';
                        ctx.fillStyle = 'rgb(54, 162, 235)';
                        ctx.textAlign = 'center';
                        ctx.fillText('Auto-Deploy', x, yAxis.top + 20);
                        ctx.fillText('Enabled', x, yAxis.top + 35);
                        ctx.restore();
                    }}
                }}
            }}]
        }});
        
    </script>
</body>
</html>
"""
    
    # Write the HTML file
    with open('autodeploy_impact_dashboard.html', 'w') as f:
        f.write(html_content)
    
    print("Dashboard created successfully!")
    print("📊 Dashboard metrics:")
    print(f"   Before auto-deploy: {before_completion_rate:.1f}% completion rate, {before_avg_days*24:.1f} hours avg")
    print(f"   After auto-deploy:  {after_completion_rate:.1f}% completion rate, {after_avg_days*24:.1f} hours avg")
    print(f"   Improvements: +{((after_completion_rate - before_completion_rate) / before_completion_rate * 100):.1f}% completion rate, {((before_avg_days - after_avg_days) / before_avg_days * 100):.1f}% faster")
    print("✅ Open 'autodeploy_impact_dashboard.html' in your browser to view the dashboard")

if __name__ == "__main__":
    create_autodeploy_dashboard()