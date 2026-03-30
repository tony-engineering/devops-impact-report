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
    <title>Auto-Deploy Impact Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 60px 20px 20px 20px; /* Top padding for fixed banner */
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }}
        
        .logo-container {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
            margin-bottom: 20px;
        }}
        
        .logo {{
            height: 60px;
            width: auto;
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            margin: 0;
        }}
        
        .header p {{
            font-size: 1.2rem;
            opacity: 0.9;
            line-height: 1.5;
            max-width: 800px;
            margin: 0 auto;
        }}
        
        .author-banner {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            padding: 8px 20px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            font-size: 0.85rem;
            text-align: center;
            z-index: 1000;
            backdrop-filter: blur(10px);
        }}
        
        .author-banner p {{
            margin: 0;
            opacity: 0.9;
        }}
        
        .author-banner a {{
            color: #84fab0;
            text-decoration: none;
        }}
        
        .author-banner a:hover {{
            text-decoration: underline;
        }}
        
        body {{
            padding-top: 40px; /* Account for fixed banner */
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .metric-card {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        }}
        
        .metric-card h3 {{
            color: #333;
            margin-bottom: 15px;
            font-size: 1.3rem;
            text-align: center;
        }}
        
        .cost-savings-card {{
            background: linear-gradient(135deg, #ffd93d 0%, #ff6b6b 100%);
            color: white;
            text-align: center;
        }}
        
        .cost-savings-card h3,
        .cost-savings-card .improvement-value,
        .cost-savings-card .improvement-desc {{
            color: white !important;
        }}
        
        .before-after {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            align-items: center;
        }}
        
        .metric-item {{
            text-align: center;
            padding: 15px;
            border-radius: 10px;
        }}
        
        .before {{
            background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
        }}
        
        .after {{
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        }}
        
        .metric-value {{
            font-size: 2rem;
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }}
        
        .metric-label {{
            font-size: 0.9rem;
            color: #666;
            margin-bottom: 3px;
        }}
        
        .improvement-card {{
            background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%);
            color: white;
            text-align: center;
        }}
        
        .improvement-value {{
            font-size: 3rem;
            font-weight: bold;
            margin-bottom: 10px;
        }}

        .improvement-value2 {{
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        
        .improvement-desc {{
            font-size: 1.1rem;
            opacity: 0.9;
        }}
        
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .chart-card {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }}
        
        .chart-card h3 {{
            color: #333;
            margin-bottom: 20px;
            text-align: center;
            font-size: 1.3rem;
        }}
        
        .autodeploy-marker {{
            position: absolute;
            background: red;
            color: white;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 0.8rem;
            transform: rotate(-15deg);
        }}
        
        .summary {{
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 30px;
            text-align: center;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }}
        
        .summary h2 {{
            color: #333;
            margin-bottom: 20px;
            font-size: 2rem;
        }}
        
        .summary p {{
            color: #666;
            font-size: 1.1rem;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
        }}
        
        .highlight {{
            color: #86f2bd;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <!-- Author info banner -->
    <div class="author-banner">
        <p>Work by <strong>Antoine ROUGEOT</strong> (Tony Engineering OÜ) | LinkedIn: <a href="https://www.linkedin.com/in/antoinerougeot/" target="_blank">antoinerougeot</a> | Source: <a href="https://github.com/Tony-Engineering-OU/devops-impact-report" target="_blank">GitHub</a></p>
    </div>
    
    <div class="container">
        <div class="header">
            <div class="logo-container">
                <img src="tonyengineering.png" alt="Tony Engineering" class="logo">
                <h1>DevOps Best Practices Impact Report</h1>
            </div>
            <p>Measuring the impact of <strong>DevOps best practices</strong> implementation for a client showing both <strong style="color: #86f2bd;">operational improvements</strong> and <strong style="color: #ffd93d;">financial impact</strong>. <strong style="color: #86f2bd;">Feature environments</strong> setup followed by <strong style="color: #86f2bd;">continuous deployment</strong> to production (<strong>Auto-Deploy</strong>) on <strong style="color: #86f2bd;">12 December 2023</strong> were a <strong>game changer</strong> in the Software Development Lifecycle.</p>
            <p>This also showcases the importance of a strong <strong>automated testing culture</strong> and constant <strong>costs management optimization</strong>.</p>
            <p>This transformation was conducted following <strong><a href="https://12factor.net/" target="_blank" style="color: #86f2bd; text-decoration: none;">12-Factor App methodology</a></strong> and <strong><a href="https://www.prisma.io/dataguide/types/relational/expand-and-contract-pattern#what-is-the-expand-and-contract-pattern" target="_blank" style="color: #86f2bd; text-decoration: none;">Expand/Contract patterns</a></strong> to minimize incidents (<strong style="color: #86f2bd;">uptime > 99%</strong> for the period 2022-2025).</p>        </div>
        <br>

        <div class="metrics-grid">
                <div class="metric-card cost-savings-card">
                    <h3>💰 Total estimated savings for devs and data scientists</h3>
                    <div class="improvement-value" id="total-savings">-</div>
                    <div class="improvement-value2" id="business-days-saved">-</div>
                    <div class="improvement-desc">For period 2024-2025. <a href="https://github.com/Tony-Engineering-OU/devops-impact-report/blob/main/cost_savings_calculator.py"  target="_blank" style="color: #ffd93d; text-decoration: none;">Calculation details</a>.</div>
                </div>
            </div>

        <div class="metrics-grid">
            

            <div class="metric-card">
                <h3>📊 Completion Rate</h3>
                <div class="before-after">
                    <div class="metric-item before">
                        <div class="metric-label">Before Auto-Deploy</div>
                        <div class="metric-value" id="before-completion">-</div>
                        <div class="metric-label">Success Rate</div>
                    </div>
                    <div class="metric-item after">
                        <div class="metric-label">After Auto-Deploy</div>
                        <div class="metric-value" id="after-completion">-</div>
                        <div class="metric-label">Success Rate</div>
                    </div>
                </div>
            </div>
            
            <div class="metric-card">
                <h3>⏱️ Average Deployment Time</h3>
                <div class="before-after">
                    <div class="metric-item before">
                        <div class="metric-label">Before Auto-Deploy</div>
                        <div class="metric-value" id="before-time">-</div>
                        <div class="metric-label">Days</div>
                    </div>
                    <div class="metric-item after">
                        <div class="metric-label">After Auto-Deploy</div>
                        <div class="metric-value" id="after-time">-</div>
                        <div class="metric-label">Days</div>
                    </div>
                </div>
            </div>
            
            <div class="metric-card improvement-card">
                <h3>🎯 Completion Rate Improvement</h3>
                <div class="improvement-value" id="completion-improvement">-</div>
                <div class="improvement-desc">More Reliable</div>
            </div>
            
            <div class="metric-card improvement-card">
                <h3>⚡ Speed Improvement</h3>
                <div class="improvement-value" id="speed-improvement">-</div>
                <div class="improvement-desc">Faster Deployments</div>
            </div>
        </div>
        
        
        
        <div class="charts-grid">
            <div class="chart-card">
                <h3>📈 Deployments success rates</h3>
                <canvas id="completionChart"></canvas>
            </div>
            
            <div class="chart-card">
                <h3>🏃‍♂️ Monthly Deployment Time Trend</h3>
                <canvas id="deploymentChart"></canvas>
            </div>
            
            <div class="chart-card">
                <h3>🧪 Test Coverage & E2E Tests Trend</h3>
                <canvas id="testChart"></canvas>
            </div>
            
            <div class="chart-card">
                <h3>💰 AWS EC2 Costs for feature environments</h3>
                <canvas id="ec2Chart"></canvas>
            </div>
            
            <div class="chart-card">
                <h3>🌿 Feature Environments Created Over Time</h3>
                <canvas id="featureEnvsChart"></canvas>
            </div>
            
            <div class="chart-card">
                <h3>🔧 Data Pipeline Failures Over Time</h3>
                <canvas id="pipelineReliabilityChart"></canvas>
            </div>
            
        </div>
        
        <div class="summary">
            <h2>🎉 Key Takeaways</h2>
            <p>
                The auto-deploy enablement on <strong>December 12, 2023</strong> resulted in a 
                <span class="highlight">15.3x more reliable deployments</span> in deployment completion rates and 
                <span class="highlight">57.3% faster deployments</span> in deployment times. 
                This transformation moved the team from manual, error-prone deployments to 
                <strong>automated, reliable, and fast</strong> continuous deployment.
            </p>
            <br>
            <p>
                The introduction of <strong>feature environments in September 2023</strong> was a mandatory step 
                to move safely to continuous deployment, providing isolated testing environments that enabled 
                confident automated deployments without production risks.
            </p>
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