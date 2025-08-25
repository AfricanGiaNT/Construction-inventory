# 📝 Entry Features Quick Guide

**Quick reference for stock IN, OUT, and batch entries**

---

## 🟢 **Stock IN Commands** (Receiving Items)

### **Single Entry**
```
/in item, quantity unit, [driver], [from_location], [note]
```

**Examples:**
- `/in cement, 50 bags, delivered by John, from supplier`
- `/in steel bars, 100 pieces, from warehouse`
- `/in safety equipment, 20 sets, from office`

### **Batch Entry** (Multiple Items)
**Set project and driver once at the top, then list items:**

**Option 1: Newlines (one item per line)**
```
/in project: Bridge, driver: Mr Longwe
cement, 50 bags
steel bars, 100 pieces
safety equipment, 20 sets
```

**Option 2: Semicolons (all items on one line)**
```
/in project: Bridge, driver: Mr Longwe
cement, 50 bags; steel bars, 100 pieces; safety equipment, 20 sets
```

**Or more items:**
```
/in project: Road Project, driver: John
cement, 100 bags; sand, 200 bags; stones, 50 tons; wire, 500 meters
```

---

## 🔴 **Stock OUT Commands** (Issuing Items)

### **Single Entry**
```
/out item, quantity unit, [to_location], [driver], [note]
```

**Examples:**
- `/out cement, 25 bags, to site A, by Mr Longwe`
- `/out steel bars, 10 pieces, to bridge project`
- `/out electrical wire, 100 meters, to office building`

### **Batch Entry** (Multiple Items)
**Set project and destination once at the top, then list items:**

**Option 1: Newlines (one item per line)**
```
/out project: Bridge, to: Site A
cement, 25 bags
steel bars, 10 pieces
safety equipment, 5 sets
```

**Option 2: Semicolons (all items on one line)**
```
/out project: Bridge, to: Site A
cement, 25 bags; steel bars, 10 pieces; safety equipment, 5 sets
```

**Or more items:**
```
/out project: Road Project, to: Warehouse
cement, 50 bags; sand, 100 bags; stones, 25 tons; wire, 200 meters
```

---

## 🟡 **Stock ADJUST Commands** (Admin Only)

### **Single Entry**
```
/adjust item, ±quantity unit, [location], [note]
```

**Examples:**
- `/adjust cement, -5 bags, warehouse, damaged bags`
- `/adjust steel bars, +10 pieces, correction`
- `/adjust safety equipment, -2 sets, lost items`

### **Batch Entry** (Multiple Items)
**Set project and location once at the top, then list items:**

**Option 1: Newlines (one item per line)**
```
/adjust project: Bridge, location: Warehouse
cement, -5 bags, damaged
steel bars, -2 pieces, lost
safety equipment, +3 sets, found
```

**Option 2: Semicolons (all items on one line)**
```
/adjust project: Bridge, location: Warehouse
cement, -5 bags, damaged; steel bars, -2 pieces, lost; safety equipment, +3 sets, found
```

**Or more items:**
```
/adjust project: Road Project, location: Site A
cement, -10 bags, water damage; sand, +20 bags, correction; stones, -5 tons, theft; wire, +100 meters, found
```

---

## 📋 **How to Write Batch Commands**

### **Step 1: Start with /in, /out, or /adjust**
```
/in
```

### **Step 2: Add project and other details (only once)**
```
/in project: Bridge Project, driver: Mr Longwe
```

### **Step 3: List your items (choose your style)**

**Style A: Newlines (easier to read)**
```
cement, 50 bags
steel bars, 100 pieces
safety equipment, 20 sets
```

**Style B: Semicolons (more compact)**
```
cement, 50 bags; steel bars, 100 pieces; safety equipment, 20 sets
```

### **Complete Examples:**

**Newline Style:**
```
/in project: Bridge Project, driver: Mr Longwe
cement, 50 bags
steel bars, 100 pieces
safety equipment, 20 sets
```

**Semicolon Style:**
```
/in project: Bridge Project, driver: Mr Longwe
cement, 50 bags; steel bars, 100 pieces; safety equipment, 20 sets
```

---

## ⚠️ **Important Rules**

- **Project is REQUIRED** - always write "project: [name]"
- **Maximum 15 items** per batch
- **Use /validate** to test your format before sending
- **Write project and driver only once** at the top
- **Choose your style**: newlines OR semicolons (don't mix them)

---

## 🚀 **Quick Commands**

- `/help` - General commands
- `/batchhelp` - Detailed batch guide
- `/validate` - Test your format
- `/status` - System overview

---

## 💡 **Simple Tips**

1. **Always start with project name**
2. **Write driver/destination once at the top**
3. **Choose one style**: newlines OR semicolons
4. **Use /validate to check before sending**
5. **Newlines are easier to read, semicolons save space**
