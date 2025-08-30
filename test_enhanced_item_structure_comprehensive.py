#!/usr/bin/env python3
"""
Comprehensive Test Suite: Enhanced Item Structure for Mixed-Size Materials

This script implements the comprehensive testing plan covering all 5 phases:
- Phase 1: Unit Testing (Schema validation, methods)
- Phase 2: Integration Testing (Service interactions)
- Phase 3: End-to-End Testing (Complete workflows)
- Phase 4: Regression Testing (Backward compatibility)
- Phase 5: Performance Testing (System performance)
"""

import sys
import os
import time
import asyncio
import statistics
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.schemas import Item, StockMovement, MovementType, MovementStatus, UserRole
from src.services.stock import StockService
from src.services.inventory import InventoryService
from src.services.batch_stock import BatchStockService
from unittest.mock import AsyncMock, MagicMock

class TestMetrics:
    """Track test execution metrics"""
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_results = []
        self.performance_baseline = {}
        self.start_time = None
        self.end_time = None
    
    def start_test_suite(self):
        self.start_time = time.time()
        print(f"🚀 Starting Comprehensive Test Suite at {datetime.now()}")
    
    def end_test_suite(self):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        print(f"\n⏱️ Test Suite completed in {duration:.2f} seconds")
        self.generate_report()
    
    def record_test(self, test_name: str, success: bool, duration: float = 0, details: str = ""):
        self.total_tests += 1
        if success:
            self.passed_tests += 1
            status = "✅ PASS"
        else:
            self.failed_tests += 1
            status = "❌ FAIL"
        
        self.test_results.append({
            "test_name": test_name,
            "success": success,
            "duration": duration,
            "details": details,
            "status": status
        })
        
        print(f"{status} {test_name} ({duration:.3f}s)")
        if details:
            print(f"   Details: {details}")
    
    def generate_report(self):
        print("\n" + "="*80)
        print("📊 COMPREHENSIVE TEST SUITE REPORT")
        print("="*80)
        print(f"Total Tests: {self.total_tests}")
        print(f"Passed: {self.passed_tests} ✅")
        print(f"Failed: {self.failed_tests} ❌")
        print(f"Success Rate: {(self.passed_tests/self.total_tests*100):.1f}%")
        
        if self.failed_tests > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test_name']}: {result['details']}")
        
        print(f"\n⏱️ PERFORMANCE BASELINE:")
        for operation, times in self.performance_baseline.items():
            if times:
                avg_time = statistics.mean(times)
                min_time = min(times)
                max_time = max(times)
                print(f"  {operation}: avg={avg_time:.3f}s, min={min_time:.3f}s, max={max_time:.3f}s")

class MockAirtable:
    """Mock Airtable service for testing"""
    def __init__(self):
        self.items = {}
        self.movements = []
        self.movement_counter = 1
        self.performance_data = {}
    
    async def get_item(self, item_name: str) -> Item:
        return self.items.get(item_name)
    
    async def create_item(self, item: Item) -> str:
        item_id = f"item_{len(self.items) + 1}"
        self.items[item.name] = item
        return item_id
    
    async def create_movement(self, movement: StockMovement) -> str:
        movement_id = f"mov_{self.movement_counter}"
        self.movement_counter += 1
        self.movements.append(movement)
        return movement_id
    
    async def update_item_stock(self, item_name: str, new_stock: float) -> bool:
        if item_name in self.items:
            self.items[item_name].on_hand = new_stock
            return True
        return False
    
    async def search_items(self, query: str) -> List[Item]:
        return [item for item in self.items.values() if query.lower() in item.name.lower()]
    
    async def get_low_stock_items(self) -> List[Item]:
        return [item for item in self.items.values() if item.threshold and item.on_hand < item.threshold]

class MockSettings:
    """Mock settings for testing"""
    def __init__(self):
        self.default_approval_threshold = 100

class MockAuditTrailService:
    """Mock audit trail service for testing"""
    async def create_audit_trail(self, batch_id: str, movements: List[StockMovement], user_id: int, user_name: str) -> str:
        return f"audit_{batch_id}"

class ComprehensiveTestSuite:
    """Main test suite class"""
    def __init__(self):
        self.metrics = TestMetrics()
        self.mock_airtable = MockAirtable()
        self.mock_settings = MockSettings()
        self.mock_audit_trail = MockAuditTrailService()
        
        # Initialize services
        self.stock_service = StockService(self.mock_airtable, self.mock_settings)
        self.inventory_service = InventoryService(self.mock_airtable, self.mock_audit_trail)
        self.batch_service = BatchStockService(self.mock_airtable, self.mock_settings, self.stock_service)
        
        # Test data
        self.test_items = {}
        self.setup_test_data()
    
    def setup_test_data(self):
        """Setup test items for comprehensive testing"""
        # Enhanced items
        self.test_items["paint_20ltr"] = Item(
            name="Paint 20ltrs",
            on_hand=0.0,
            base_unit="piece",
            unit_size=20.0,
            unit_type="ltrs",
            threshold=5.0,
            large_qty_threshold=50.0,
            location="Warehouse A",
            category="Paint",
            sku="PAINT-20L",
            units=[]
        )
        
        self.test_items["paint_5ltr"] = Item(
            name="Paint 5ltrs",
            on_hand=0.0,
            base_unit="piece",
            unit_size=5.0,
            unit_type="ltrs",
            threshold=10.0,
            large_qty_threshold=100.0,
            location="Warehouse B",
            category="Paint",
            sku="PAINT-5L",
            units=[]
        )
        
        self.test_items["cement_25kg"] = Item(
            name="Cement 25kg",
            on_hand=0.0,
            base_unit="piece",
            unit_size=25.0,
            unit_type="kg",
            threshold=20.0,
            large_qty_threshold=500.0,
            location="Warehouse C",
            category="Construction",
            sku="CEMENT-25KG",
            units=[]
        )
        
        # Regular items (backward compatibility)
        self.test_items["screwdriver"] = Item(
            name="Screwdriver",
            on_hand=0.0,
            base_unit="piece",
            unit_size=1.0,
            unit_type="piece",
            threshold=20.0,
            large_qty_threshold=200.0,
            location="Tool Room",
            category="Tools",
            sku="TOOL-001",
            units=[]
        )
    
    async def run_phase1_unit_tests(self):
        """Phase 1: Unit Testing"""
        print("\n🔬 PHASE 1: UNIT TESTING")
        print("="*50)
        
        # Test 1.1: Schema Validation
        start_time = time.time()
        try:
            # Test enhanced item schema
            item = self.test_items["paint_20ltr"]
            assert item.unit_size == 20.0
            assert item.unit_type == "ltrs"
            assert item.get_total_volume() == 0.0  # on_hand = 0
            
            # Test regular item schema
            regular_item = self.test_items["screwdriver"]
            assert regular_item.unit_size == 1.0
            assert regular_item.unit_type == "piece"
            
            duration = time.time() - start_time
            self.metrics.record_test("Schema Validation", True, duration, "Enhanced and regular schemas working correctly")
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_test("Schema Validation", False, duration, f"Error: {str(e)}")
        
        # Test 1.2: Enhanced Item Methods
        start_time = time.time()
        try:
            # Test total volume calculation
            item = self.test_items["paint_20ltr"]
            item.on_hand = 5.0
            total_volume = item.get_total_volume()
            assert total_volume == 100.0  # 5 × 20 = 100
            
            # Test unit extraction (simulated)
            assert item.unit_size == 20.0
            assert item.unit_type == "ltrs"
            
            duration = time.time() - start_time
            self.metrics.record_test("Enhanced Item Methods", True, duration, "Total volume calculation and unit extraction working")
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_test("Enhanced Item Methods", False, duration, f"Error: {str(e)}")
    
    async def run_phase2_integration_tests(self):
        """Phase 2: Integration Testing"""
        print("\n🔗 PHASE 2: INTEGRATION TESTING")
        print("="*50)
        
        # Test 2.1: Stock Service Integration
        start_time = time.time()
        try:
            # Create items in mock Airtable
            for item in self.test_items.values():
                await self.mock_airtable.create_item(item)
            
            # Test stock in integration
            success, message, before, after = await self.stock_service.stock_in(
                "Paint 20ltrs", 3, None, "Warehouse A", "Test stock in", 1, "TestUser"
            )
            assert success == True
            assert "3 units × 20.0 ltrs = 60.0 ltrs" in message
            
            # Simulate stock update for testing
            await self.mock_airtable.update_item_stock("Paint 20ltrs", after)
            
            duration = time.time() - start_time
            self.metrics.record_test("Stock Service Integration", True, duration, "Stock in operation with enhanced unit context working")
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_test("Stock Service Integration", False, duration, f"Error: {str(e)}")
        
        # Test 2.2: Batch Stock Service Integration
        start_time = time.time()
        try:
            # Test batch operations
            movements = [
                StockMovement(
                    item_name="Paint 5ltrs",
                    movement_type=MovementType.IN,
                    quantity=10,
                    unit="piece",
                    signed_base_quantity=10,
                    unit_size=5.0,
                    unit_type="ltrs",
                    user_id="1",
                    user_name="TestUser",
                    timestamp=datetime.now(timezone.utc)
                )
            ]
            
            # Test batch approval preparation
            success, message, batch_approval = await self.batch_service.prepare_batch_approval(
                movements, UserRole.STAFF, 123, 1, "TestUser"
            )
            assert success == True
            
            duration = time.time() - start_time
            self.metrics.record_test("Batch Stock Service Integration", True, duration, "Batch operations with enhanced items working")
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_test("Batch Stock Service Integration", False, duration, f"Error: {str(e)}")
    
    async def run_phase3_end_to_end_tests(self):
        """Phase 3: End-to-End Testing"""
        print("\n🌐 PHASE 3: END-TO-END TESTING")
        print("="*50)
        
        # Test 3.1: Complete Mixed-Size Workflow
        start_time = time.time()
        try:
            # Reset stock levels for clean testing
            await self.mock_airtable.update_item_stock("Paint 20ltrs", 0.0)
            await self.mock_airtable.update_item_stock("Paint 5ltrs", 0.0)
            
            # Stock in operations for mixed sizes
            success1, message1, before1, after1 = await self.stock_service.stock_in(
                "Paint 20ltrs", 5, None, "Warehouse A", "Initial stock", 1, "TestUser"
            )
            assert success1 == True
            await self.mock_airtable.update_item_stock("Paint 20ltrs", after1)
            
            success2, message2, before2, after2 = await self.stock_service.stock_in(
                "Paint 5ltrs", 20, None, "Warehouse B", "Initial stock", 1, "TestUser"
            )
            assert success2 == True
            await self.mock_airtable.update_item_stock("Paint 5ltrs", after2)
            
            # Verify total volumes
            paint_20ltr = await self.mock_airtable.get_item("Paint 20ltrs")
            paint_5ltr = await self.mock_airtable.get_item("Paint 5ltrs")
            
            total_20ltr = paint_20ltr.get_total_volume()
            total_5ltr = paint_5ltr.get_total_volume()
            combined_total = total_20ltr + total_5ltr
            
            assert total_20ltr == 100.0, f"Expected 100.0, got {total_20ltr}"
            assert total_5ltr == 100.0, f"Expected 100.0, got {total_5ltr}"
            assert combined_total == 200.0, f"Expected 200.0, got {combined_total}"
            
            duration = time.time() - start_time
            self.metrics.record_test("Complete Mixed-Size Workflow", True, duration, f"Total volume: {combined_total} ltrs")
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_test("Complete Mixed-Size Workflow", False, duration, f"Error: {str(e)}")
            print(f"Debug - Exception details: {type(e).__name__}: {str(e)}")
        
        # Test 3.2: Mixed Item Types Workflow
        start_time = time.time()
        try:
            # Test with both enhanced and regular items
            success3, message3, before3, after3 = await self.stock_service.stock_in(
                "Screwdriver", 50, None, "Tool Room", "Initial stock", 1, "TestUser"
            )
            await self.mock_airtable.update_item_stock("Screwdriver", after3)
            
            # Verify both types work together
            enhanced_item = await self.mock_airtable.get_item("Paint 20ltrs")
            regular_item = await self.mock_airtable.get_item("Screwdriver")
            
            assert enhanced_item.unit_size > 1.0
            assert regular_item.unit_size == 1.0
            
            duration = time.time() - start_time
            self.metrics.record_test("Mixed Item Types Workflow", True, duration, "Enhanced and regular items working together")
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_test("Mixed Item Types Workflow", False, duration, f"Error: {str(e)}")
    
    async def run_phase4_regression_tests(self):
        """Phase 4: Regression Testing"""
        print("\n🔄 PHASE 4: REGRESSION TESTING")
        print("="*50)
        
        # Test 4.1: Backward Compatibility
        start_time = time.time()
        try:
            # Test existing functionality still works
            success, message, item = await self.stock_service.get_current_stock("Screwdriver")
            assert success == True, f"Expected success=True, got {success}"
            assert "Current stock: 50" in message, f"Expected 'Current stock: 50' in message, got '{message}'"
            
            # Test search functionality
            success, message, items = await self.stock_service.search_items("Paint")
            assert success == True
            assert len(items) == 2  # Paint 20ltrs and Paint 5ltrs
            
            duration = time.time() - start_time
            self.metrics.record_test("Backward Compatibility", True, duration, "Existing functionality maintained")
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_test("Backward Compatibility", False, duration, f"Error: {str(e)}")
            print(f"Debug - Backward Compatibility Exception: {type(e).__name__}: {str(e)}")
        
        # Test 4.2: API Compatibility
        start_time = time.time()
        try:
            # Test all stock operations still work
            success, message, movement_id, before, after = await self.stock_service.stock_out(
                "Paint 20ltrs", 2, None, "Warehouse A", "Test stock out", 1, "TestUser", UserRole.STAFF
            )
            assert success == True
            assert "2 units × 20.0 ltrs = 40.0 ltrs" in message
            
            duration = time.time() - start_time
            self.metrics.record_test("API Compatibility", True, duration, "All stock operations working correctly")
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_test("API Compatibility", False, duration, f"Error: {str(e)}")
            print(f"Debug - API Compatibility Exception: {type(e).__name__}: {str(e)}")
    
    async def run_phase5_performance_tests(self):
        """Phase 5: Performance Testing"""
        print("\n⚡ PHASE 5: PERFORMANCE TESTING")
        print("="*50)
        
        # Test 5.1: Database Performance
        start_time = time.time()
        try:
            # Test multiple operations for performance baseline
            operation_times = []
            
            for i in range(10):
                op_start = time.time()
                await self.stock_service.get_current_stock("Paint 20ltrs")
                operation_times.append(time.time() - op_start)
            
            avg_time = statistics.mean(operation_times)
            assert avg_time < 0.1  # Should be very fast with mock data
            
            self.metrics.performance_baseline["get_current_stock"] = operation_times
            
            duration = time.time() - start_time
            self.metrics.record_test("Database Performance", True, duration, f"Average operation time: {avg_time:.3f}s")
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_test("Database Performance", False, duration, f"Error: {str(e)}")
        
        # Test 5.2: System Performance
        start_time = time.time()
        try:
            # Test batch operations performance
            batch_times = []
            
            for i in range(5):
                op_start = time.time()
                movements = [
                    StockMovement(
                        item_name="Paint 5ltrs",
                        movement_type=MovementType.IN,
                        quantity=1,
                        unit="piece",
                        signed_base_quantity=1,
                        unit_size=5.0,
                        unit_type="ltrs",
                        user_id="1",
                        user_name="TestUser",
                        timestamp=datetime.now(timezone.utc)
                    )
                ]
                
                success, message, batch_approval = await self.batch_service.prepare_batch_approval(
                    movements, UserRole.STAFF, 123, 1, "TestUser"
                )
                batch_times.append(time.time() - op_start)
            
            avg_batch_time = statistics.mean(batch_times)
            assert avg_batch_time < 0.2  # Should be reasonably fast
            
            self.metrics.performance_baseline["batch_preparation"] = batch_times
            
            duration = time.time() - start_time
            self.metrics.record_test("System Performance", True, duration, f"Average batch time: {avg_batch_time:.3f}s")
        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_test("System Performance", False, duration, f"Error: {str(e)}")
    
    async def run_comprehensive_test_suite(self):
        """Run the complete comprehensive test suite"""
        self.metrics.start_test_suite()
        
        try:
            # Execute all testing phases
            await self.run_phase1_unit_tests()
            await self.run_phase2_integration_tests()
            await self.run_phase3_end_to_end_tests()
            await self.run_phase4_regression_tests()
            await self.run_phase5_performance_tests()
            
        except Exception as e:
            print(f"❌ Test suite execution failed: {str(e)}")
            raise
        
        finally:
            self.metrics.end_test_suite()

async def main():
    """Main test execution function"""
    print("🧪 COMPREHENSIVE TEST SUITE: Enhanced Item Structure")
    print("="*80)
    print("This test suite validates all 5 phases of the enhanced item structure implementation")
    print("including unit testing, integration testing, end-to-end testing, regression testing,")
    print("and performance testing.")
    print("="*80)
    
    test_suite = ComprehensiveTestSuite()
    await test_suite.run_comprehensive_test_suite()

if __name__ == "__main__":
    asyncio.run(main())
