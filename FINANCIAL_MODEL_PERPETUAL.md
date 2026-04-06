# TCO/ROI Financial Model - Perpetual Licenses Support

## Overview

The Modernization Factory now includes a sophisticated financial model that properly accounts for **perpetual licenses**, contrasting them with annual licenses and calculating realistic **Total Cost of Ownership (TCO)** and **Return on Investment (ROI)**.

## Problem Statement

**Previous Model (SIMPLISTIC):**
```javascript
var opex = 500 + cr * 150;  // Only based on critical findings count
var migrationCost = cr * 3500;
var payback = migrationCost / opex;  // Simple division
```

**Issues:**
- ❌ Treated all licenses as annual (divided by 12)
- ❌ No perpetual license detection
- ❌ Ignored maintenance/support costs (20-30% of perpetual value)
- ❌ No labor costs (DBA, sysadmin, support team)
- ❌ No amortization schedule for perpetual licenses
- ❌ Missing hidden overhead costs
- ❌ Inaccurate for enterprise infrastructure with Oracle, IBM, etc.

---

## Enhanced Model - Component Architecture

### 1. License Metadata (Added to Each Signature)

Each signature now includes three license fields:

```javascript
{
  id: 'oracle',
  licType: 'perpetual',  // 'perpetual' | 'annual' | 'free'
  licCost: 250000        // Annual equivalent cost in USD
}
```

**License Type Classification:**

| Type | Definition | Examples | Cost Model |
|------|-----------|----------|-----------|
| **perpetual** | One-time purchase + annual maintenance | Oracle DB, WebSphere, OSB, ODI | Amortized 5yr + 25% support |
| **annual** | Yearly subscription/SaaS | NetBackup, WebSphere, Veritas | Direct annual cost |
| **free** | Open source / no licensing costs | Java, NiFi, Tomcat, JBoss | $0 |

### 2. License Cost Estimates by Technology

```javascript
EXPENSIVE PERPETUAL (Oracle Ecosystem):
  Oracle Database:        $250,000 perpetual
  Oracle Service Bus:     $75,000 perpetual
  Oracle Data Integrator: $65,000 perpetual
  Oracle JRockit:         $40,000 perpetual

MODERATE PERPETUAL:
  IBM WebSphere:          $120,000 annual
  VMware CAF:             $85,000 perpetual
  Veritas PBX:            $55,000 perpetual
  ManageSoft:             $30,000 perpetual

MODERATE ANNUAL:
  Veritas NetBackup:      $45,000 annual

OPEN SOURCE (FREE):
  NiFi, Tomcat, JBoss, PHP, Node.js, Python, etc.
```

### 3. Amortization Schedule for Perpetual Licenses

Perpetual licenses are amortized over **5 years** (industry standard):

```
Perpetual License Cost → Annual OpEx

Example: Oracle Database ($250K perpetual)
  Annual Amortization: $250K / 5 = $50K/year
  Annual Maintenance:  $250K * 25% / 5 = $12.5K/year
  Total Annual OpEx:   $62.5K/year
```

### 4. Labor Cost Structure

Essential operational labor costs:

```javascript
LABOR_COSTS {
  if (CRITICAL_FINDINGS > 0):    +$150,000/year (DBA expertise)
  if (HIGH_FINDINGS > 0):         +$80,000/year (System admin)
  BASE_SUPPORT:                   +$50,000/year (On-call support)
  Total Baseline:                 $50K minimum
}
```

These are **on-prem costs only** reduced by 70% in cloud modernization.

### 5. TCO Calculation Formula

```
CURRENT STATE (Legacy On-Prem):
  ├─ Infrastructure Base:     $500/month = $6K/year
  ├─ License Amortization:    (Perpetual/5) + (Perpetual*0.25/5)
  ├─ Annual Licenses:         Direct annual cost
  ├─ Labor Costs:             $50K - $280K/year
  └─ TOTAL ANNUAL OpEx:       Sum of all above

MODERNIZED STATE (Cloud Native):
  ├─ Infrastructure Base:     $500/month = $6K/year (ALB, monitoring)
  ├─ License Amortization:    $0 (open-source)
  ├─ Annual Licenses:         $0 (AWS-managed)
  ├─ Labor Costs:             30% of legacy (fully automated)
  └─ TOTAL ANNUAL OpEx:       ~$6K + (Labor * 0.3)

MONTHLY OPEX:
  Current = (Total Annual OpEx) / 12
  Modern:  = (Total Annual OpEx Modern) / 12
  Saving:  = Current - Modern
```

### 6. ROI Calculation

```
MIGRATION INVESTMENT:
  = (Critical Findings * $4,500) + (High Findings * $2,500)
  
  Typical: 2 Critical + 1 High
  = (2 * $4,500) + (1 * $2,500) = $11,500

PAYBACK PERIOD:
  = Migration Investment / Monthly Savings
  
  Example: $11,500 / $1,200/month = ~9.6 months

5-YEAR TCO COMPARISON:
  Legacy:     Current OpEx * 60 months
  Modernized: Modern OpEx * 60 months
  Net Saving: (Legacy - Modernized - Migration Cost)
  
  ROI % = (Total 5yr Savings / Investment) * 100
```

---

## Implementation Details

### Updated Analyze() Function

```javascript
// Calculate detected licenses by type
var perpLic = 0, annualLic = 0, freeLic = 0;
fi.forEach(function(f) {
  var s = SIGS.find(sig => sig.id === f.id);
  if (s) {
    if (s.licType === 'perpetual') perpLic += s.licCost;
    else if (s.licType === 'annual') annualLic += s.licCost;
  }
});

// Perpetual license amortization (5 years)
var amortYears = 5, maintenanceRate = 0.25;
var perpetualAmort = (perpLic / amortYears);
var maintenance = (perpLic * maintenanceRate) / amortYears;
var totalLicYear = perpetualAmort + maintenance + annualLic;

// Labor costs
var laborCosts = 0;
if (cr > 0) laborCosts += 150000;      // DBA
if (hi > 0) laborCosts += 80000;       // SysAdmin
laborCosts += 50000;                   // Base support

// Monthly OPEX
var totalOpEx = 500 + totalLicYear/12 + laborCosts/12;
var annualTco = totalOpEx * 12;

// Modernized state (70% labor reduction)
var modernOpEx = 500 + (laborCosts * 0.3) / 12;
var modernTco = modernOpEx * 12;

// Savings and payback
var monthlySaving = totalOpEx - modernOpEx;
var migrationCost = cr * 4500 + hi * 2500;
var paybackMonths = monthlySaving > 0 
  ? Math.round(migrationCost / monthlySaving) 
  : 999;

// 5-year comparison
var fiveYearTco = (totalOpEx * 60) / 1000;      // in K
var fiveYearModern = (modernOpEx * 60) / 1000;  // in K
var roiPct = ((annualSaving * 5 - migrationCost) / annualSaving) * 100;
```

### UI Display - TCO Breakdown Table

When user clicks "Detalles" button on TCO & ROI card:

| Metric | Display | Color |
|--------|---------|-------|
| Lic. Perpetua | Annual amortized cost | Blue |
| Lic. Anual | Direct annual cost | Blue |
| Costos Laborales (año) | Total labor spend | Yellow |
| TCO 5 años (Legacy) | Current 5-year total | Red |
| TCO 5 años (Moderno) | Modern 5-year total | Green |
| Ahorro Total 5 años | Difference - Migration | Green |
| ROI % | Return percentage | Green |

---

## Example Scenarios

### Scenario 1: Oracle Database Legacy System

```
Detected Signatures:
  - Oracle Database (perpetual, $250K)
  - Java 8 (free)
  - JSP (free)
  - SOAP/Axis (free)
  Critical Findings: 1

Calculation:
  Perpetual Amort: $250K / 5 = $50K/year
  Maintenance:     $250K * 25% / 5 = $12.5K/year
  Labor (DBA req): $150K + $50K = $200K/year
  Infrastructure:  $6K/year
  
  TOTAL ANNUAL OpEx: $268.5K/year = $22,375/month
  
Modernized (Aurora PostgreSQL):
  Labor (30% of legacy): $60K/year
  Infrastructure:        $6K/year
  
  TOTAL ANNUAL OpEx: $66K/year = $5,500/month
  
Monthly Saving: $22,375 - $5,500 = $16,875/month
Migration Cost: 1 * $4,500 = $4,500
Payback Period: $4,500 / $16,875 = 0.27 months (1 week)
5-Year Saving: ($268.5K - $66K) * 5 - $4.5K = $1,007,500
ROI: ($1.007M / $4.5K) * 100 = 22,355%
```

### Scenario 2: WebSphere + NiFi (Annual License)

```
Detected Signatures:
  - IBM WebSphere (annual, $120K)
  - Apache NiFi (free)
  - Java 8 (free)
  Critical Findings: 1
  High Findings: 1

Calculation:
  Annual Licenses: $120K/year
  Labor (DBA+Admin): $150K + $80K + $50K = $280K/year
  Infrastructure: $6K/year
  
  TOTAL ANNUAL OpEx: $406K/year = $33,833/month
  
Modernized (ECS Fargate + Lambda):
  Labor (30%): $84K/year
  Infrastructure: $6K/year
  
  TOTAL ANNUAL OpEx: $90K/year = $7,500/month
  
Monthly Saving: $33,833 - $7,500 = $26,333/month
Migration Cost: (1 * $4,500) + (1 * $2,500) = $7,000
Payback Period: $7,000 / $26,333 = 0.27 months (~1 week)
5-Year Saving: ($406K - $90K) * 5 - $7K = $1,586,000
ROI: ($1.586M / $7K) * 100 = 22,657%
```

---

## Key Assumptions & Considerations

### Conservative Estimates

1. **Labor Costs**: Based on enterprise market rates
   - DBA: $150K/year (Oracle expertise premium)
   - SysAdmin: $80K/year
   - Base Support: $50K/year

2. **Amortization**: Uses 5-year standard lifecycle
   - Could be 3-7 years depending on contract
   - Maintenance at 25% is conservative for Oracle/IBM

3. **Modernization Efficiency**: 70% labor reduction
   - Cloud automation, serverless reduces manual ops
   - On-call requirements drop significantly
   - SaaS managed services eliminate infrastructure team

4. **Migration Costs**:
   - CRITICAL issue: $4,500 per finding
   - HIGH issue: $2,500 per finding
   - Includes assessment, refactoring, testing

### What NOT Included

- Hardware refresh cycles (usually covered in infrastructure budget)
- Training costs for modernization
- Potential downtime during migration
- Third-party integration services
- License audit/compliance costs (already in perpetual amort)

---

## Perpetual License Detection Logic

The model automatically detects perpetual licenses through signature matches:

```javascript
// Oracle ecosystem = high-cost perpetual
Oracle Database        → $250K perpetual
Oracle Service Bus     → $75K perpetual
Oracle Data Integrator → $65K perpetual

// Other expensive perpetual products
IBM WebSphere         → $120K annual (treated similarly)
VMware CAF            → $85K perpetual
Veritas               → $55K perpetual
ManageSoft            → $30K perpetual

// Free/Open source = $0
NiFi, Tomcat, JBoss, Struts, Axis, SVN, etc.
```

---

## Next Steps for Enhancement

1. **User Input**: Allow manual license cost overrides
2. **Regional Pricing**: Adjust labor costs by region/country
3. **Amortization Schedule**: Let users choose 3/5/7 year schedules
4. **Hidden Costs**: Add software audit, compliance, training provisions
5. **Scenario Comparison**: "What if" analysis with different tech stacks
6. **Cloud Cost Calculator**: Integrate AWS/Azure pricing directly
7. **Historical Data**: Track TCO trends and actual migration costs

---

## Database of License Values

All signature objects include:

```javascript
{
  licType: 'perpetual|annual|free',
  licCost: number_in_usd
}

// Currently configured:
PERPETUAL: Oracle=250K, OSB=75K, ODI=65K, VMware=85K, Veritas=55K, JRockit=40K, ManageSoft=30K
ANNUAL: WebSphere=120K, NetBackup=45K
FREE: NiFi, Tomcat, JBoss, Java, Node, Python, PHP, Struts, Axis, SVN, MongoDB, ES, etc.
```

This can be updated centrally as enterprise licensing terms change.
