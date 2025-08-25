# 🔧 Items Table Restructuring Guide

## 📋 **Current vs. Target Structure**

### **Current Items Table:** 18 fields
- **Essential Fields (8):** Name, Base Unit, Category, On Hand, Reorder Level, Preferred Location, Large Qty Threshold, Is Active
- **Fields to Remove (10):** Aliases, Last Movement, Days Since Last Movement, Stock Status, Total Alternative Units, Item Units, Most Recent Movement Note, Stock Movements, Low Stock Alert (AI), Category Insights (AI)

### **Target Items Table:** 8 fields
1. **`Name`** - Item name (primary identifier)
2. **`Base Unit`** - Primary unit (pieces, meters, bags, etc.)
3. **`Category`** - Item type (Steel, Cement, Electrical, etc.)
4. **`On Hand`** - Current stock quantity
5. **`Reorder Level`** - Low stock threshold
6. **`Preferred Location`** - Default storage location
7. **`Large Qty Threshold`** - Approval threshold
8. **`Is Active`** - Item status

## 🗑️ **Manual Steps Required**

### **1. Go to Your Airtable Base**
- Open your Airtable base: `app9QmJFHvy1rcQv3`

### **2. Open the Items Table**
- Navigate to the "Items" table

### **3. Delete These 10 Fields:**
- `Aliases`
- `Last Movement`
- `Days Since Last Movement`
- `Stock Status`
- `Total Alternative Units`
- `Item Units`
- `Most Recent Movement Note`
- `Stock Movements`
- `Low Stock Alert (AI)`
- `Category Insights (AI)`

### **4. Keep Only These 8 Fields:**
- `Name`
- `Base Unit`
- `Category`
- `On Hand`
- `Reorder Level`
- `Preferred Location`
- `Large Qty Threshold`
- `Is Active`

## 🚀 **New Bot Features**

### **✅ Automatic Item Creation**
- When you receive inventory for an unknown item, the bot automatically creates a new item record
- **Example:** `/in new safety equipment, 50 pieces, from supplier`
- Bot creates: "new safety equipment" with default settings

### **✅ Automatic Stock Updates**
- Stock quantities are automatically updated when movements are recorded
- No more manual stock counting!

### **✅ Smart Stock Status**
- Stock status is calculated automatically:
  - **Normal:** On Hand > Reorder Level
  - **Low Stock:** On Hand ≤ Reorder Level
  - **Out of Stock:** On Hand = 0

### **✅ Simplified Commands**
- No more SKU requirements
- Use natural item names: `/in cement, 100 bags, from supplier`
- Flexible separators: commas, hyphens, or "and"

## 📝 **Updated Command Examples**

### **Stock In (Auto-creates new items):**
```bash
/in cement, 100 bags, delivered by John, from main supplier
/in steel bars, 50 pieces, from warehouse, by Mr Banda
/in new safety equipment, 20 pieces, from Lilongwe office
```

### **Stock Out:**
```bash
/out cement, 25 bags, to site A, by Mr Longwe
/out steel bars, 10 pieces, to bridge project, by contractor
/out electrical wire, 100 meters, to office building
```

### **Stock Adjustment:**
```bash
/adjust cement, -5 bags, warehouse, correction for damaged bags
```

## 🔄 **What Happens Automatically**

1. **Item Lookup:** Bot searches for item by name
2. **Auto-Creation:** If item doesn't exist, creates new record with defaults
3. **Movement Recording:** Records the stock movement with all details
4. **Stock Update:** Automatically updates item's "On Hand" quantity
5. **Status Calculation:** Calculates stock status based on thresholds

## ⚠️ **Important Notes**

- **Data Loss Warning:** Deleting fields will permanently remove all data in those fields
- **Backup:** The restructuring script has backed up your essential data
- **Testing:** Test the bot after restructuring to ensure everything works
- **Rollback:** If issues arise, you can restore from Airtable's version history

## 🎯 **Benefits After Restructuring**

1. **Simplified Management:** Only essential fields to maintain
2. **Auto-Inventory:** New items created automatically
3. **Real-Time Updates:** Stock quantities always current
4. **Natural Language:** Use item names instead of SKUs
5. **Reduced Errors:** Less manual data entry = fewer mistakes

## 🚀 **Next Steps**

1. **Complete Manual Restructuring** in Airtable
2. **Test the Bot** with simple commands
3. **Verify Auto-Creation** with new items
4. **Check Stock Updates** are working correctly
5. **Train Your Team** on new command format

---

**Need Help?** The bot code has been updated to work with the new structure. All SKU references have been replaced with item names, and automatic features are enabled.

