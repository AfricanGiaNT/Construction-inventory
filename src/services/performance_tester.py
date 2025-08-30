"""Performance testing service for the Construction Inventory Bot."""

import logging
import time
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC
import random

from schemas import Item
from airtable_client import AirtableClient
from services.category_parser import category_parser
from services.stock_query import StockQueryService
from services.queries import QueryService

logger = logging.getLogger(__name__)


class PerformanceTester:
    """Service for testing system performance with large datasets and multiple operations."""
    
    def __init__(self, airtable_client: AirtableClient):
        """Initialize the performance tester."""
        self.airtable = airtable_client
        self.stock_query_service = StockQueryService(airtable_client)
        self.query_service = QueryService(airtable_client)
        self.performance_results: Dict[str, Any] = {}
    
    async def run_performance_tests(self, test_scenarios: List[str] = None) -> Dict[str, Any]:
        """
        Run comprehensive performance tests.
        
        Args:
            test_scenarios: List of specific tests to run (None = run all)
            
        Returns:
            Dictionary with performance test results
        """
        if test_scenarios is None:
            test_scenarios = [
                "category_parsing",
                "search_operations",
                "reporting_generation",
                "concurrent_operations",
                "large_dataset_handling"
            ]
        
        logger.info(f"Starting performance tests: {test_scenarios}")
        
        test_results = {
            "test_timestamp": datetime.now(UTC),
            "scenarios_tested": test_scenarios,
            "results": {},
            "summary": {}
        }
        
        # Run each test scenario
        for scenario in test_scenarios:
            if scenario == "category_parsing":
                test_results["results"][scenario] = await self._test_category_parsing()
            elif scenario == "search_operations":
                test_results["results"][scenario] = await self._test_search_operations()
            elif scenario == "reporting_generation":
                test_results["results"][scenario] = await self._test_reporting_generation()
            elif scenario == "concurrent_operations":
                test_results["results"][scenario] = await self._test_concurrent_operations()
            elif scenario == "large_dataset_handling":
                test_results["results"][scenario] = await self._test_large_dataset_handling()
        
        # Generate summary
        test_results["summary"] = self._generate_performance_summary(test_results["results"])
        
        # Store results
        self.performance_results = test_results
        
        logger.info("Performance tests completed")
        return test_results
    
    async def _test_category_parsing(self) -> Dict[str, Any]:
        """Test category parsing performance."""
        test_items = [
            "Paint 20ltrs Interior White",
            "Copper Wire 100m 2.5mm",
            "PVC Pipe 3m 50mm",
            "Hammer 2kg Claw",
            "Safety Helmet Yellow",
            "Steel Bar 12mm 6m",
            "Electrical Switch Single Pole",
            "Plumbing Fitting 90 Degree",
            "Wood Screw 4x50mm",
            "LED Bulb 9W Warm White"
        ]
        
        start_time = time.time()
        parsing_results = []
        
        for item in test_items:
            item_start = time.time()
            category = category_parser.parse_category(item)
            item_time = time.time() - item_start
            
            parsing_results.append({
                "item": item,
                "category": category,
                "parse_time_ms": item_time * 1000
            })
        
        total_time = time.time() - start_time
        avg_time = total_time / len(test_items)
        
        return {
            "test_type": "category_parsing",
            "items_tested": len(test_items),
            "total_time_seconds": total_time,
            "average_time_seconds": avg_time,
            "average_time_ms": avg_time * 1000,
            "items_per_second": len(test_items) / total_time,
            "detailed_results": parsing_results
        }
    
    async def _test_search_operations(self) -> Dict[str, Any]:
        """Test search operation performance."""
        search_queries = [
            "paint",
            "electrical",
            "tools",
            "safety",
            "steel",
            "plumbing",
            "carpentry",
            "wire",
            "pipe",
            "hammer"
        ]
        
        start_time = time.time()
        search_results = []
        
        for query in search_queries:
            query_start = time.time()
            
            # Test category search
            category_results = category_parser.search_categories(query)
            
            # Test fuzzy search (if available)
            try:
                fuzzy_results = await self.stock_query_service.fuzzy_search_items(query, limit=5)
                fuzzy_count = len(fuzzy_results)
            except:
                fuzzy_count = 0
            
            query_time = time.time() - query_start
            
            search_results.append({
                "query": query,
                "category_results": len(category_results),
                "fuzzy_results": fuzzy_count,
                "query_time_ms": query_time * 1000
            })
        
        total_time = time.time() - start_time
        avg_time = total_time / len(search_queries)
        
        return {
            "test_type": "search_operations",
            "queries_tested": len(search_queries),
            "total_time_seconds": total_time,
            "average_time_seconds": avg_time,
            "average_time_ms": avg_time * 1000,
            "queries_per_second": len(search_queries) / total_time,
            "detailed_results": search_results
        }
    
    async def _test_reporting_generation(self) -> Dict[str, Any]:
        """Test reporting generation performance."""
        report_types = [
            "category_overview",
            "category_statistics",
            "category_inventory_summary"
        ]
        
        start_time = time.time()
        report_results = []
        
        for report_type in report_types:
            report_start = time.time()
            
            try:
                if report_type == "category_overview":
                    result = await self.stock_query_service.get_category_overview()
                elif report_type == "category_statistics":
                    result = await self.query_service.get_category_statistics()
                elif report_type == "category_inventory_summary":
                    result = await self.query_service.get_category_based_inventory_summary()
                
                report_time = time.time() - report_start
                
                report_results.append({
                    "report_type": report_type,
                    "success": True,
                    "data_size": len(str(result)),
                    "generation_time_ms": report_time * 1000
                })
                
            except Exception as e:
                report_time = time.time() - report_start
                report_results.append({
                    "report_type": report_type,
                    "success": False,
                    "error": str(e),
                    "generation_time_ms": report_time * 1000
                })
        
        total_time = time.time() - start_time
        avg_time = total_time / len(report_types)
        
        return {
            "test_type": "reporting_generation",
            "reports_tested": len(report_types),
            "total_time_seconds": total_time,
            "average_time_seconds": avg_time,
            "average_time_ms": avg_time * 1000,
            "reports_per_second": len(report_types) / total_time,
            "detailed_results": report_results
        }
    
    async def _test_concurrent_operations(self) -> Dict[str, Any]:
        """Test concurrent operation performance."""
        operations = [
            ("category_search", "paint"),
            ("category_search", "electrical"),
            ("category_search", "tools"),
            ("fuzzy_search", "wire"),
            ("fuzzy_search", "pipe"),
            ("category_overview", None),
            ("category_statistics", None)
        ]
        
        start_time = time.time()
        
        # Create tasks for concurrent execution
        tasks = []
        for op_type, param in operations:
            if op_type == "category_search":
                task = self._execute_category_search(param)
            elif op_type == "fuzzy_search":
                task = self._execute_fuzzy_search(param)
            elif op_type == "category_overview":
                task = self._execute_category_overview()
            elif op_type == "category_statistics":
                task = self._execute_category_statistics()
            
            tasks.append(task)
        
        # Execute all tasks concurrently
        concurrent_start = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        concurrent_time = time.time() - concurrent_start
        
        # Execute same operations sequentially for comparison
        sequential_start = time.time()
        sequential_results = []
        for op_type, param in operations:
            try:
                if op_type == "category_search":
                    result = await self._execute_category_search(param)
                elif op_type == "fuzzy_search":
                    result = await self._execute_fuzzy_search(param)
                elif op_type == "category_overview":
                    result = await self._execute_category_overview()
                elif op_type == "category_statistics":
                    result = await self._execute_category_statistics()
                
                sequential_results.append(result)
            except Exception as e:
                sequential_results.append(f"Error: {e}")
        
        sequential_time = time.time() - sequential_start
        
        return {
            "test_type": "concurrent_operations",
            "operations_tested": len(operations),
            "concurrent_time_seconds": concurrent_time,
            "sequential_time_seconds": sequential_time,
            "speedup_factor": sequential_time / concurrent_time if concurrent_time > 0 else 0,
            "concurrent_ops_per_second": len(operations) / concurrent_time,
            "sequential_ops_per_second": len(operations) / sequential_time
        }
    
    async def _test_large_dataset_handling(self) -> Dict[str, Any]:
        """Test handling of large datasets."""
        # Generate test data
        test_items = self._generate_test_items(100)
        
        start_time = time.time()
        
        # Test category parsing for large dataset
        parsing_start = time.time()
        categories = []
        for item in test_items:
            category = category_parser.parse_category(item)
            categories.append(category)
        parsing_time = time.time() - parsing_start
        
        # Test category grouping
        grouping_start = time.time()
        category_groups = {}
        for item, category in zip(test_items, categories):
            if category not in category_groups:
                category_groups[category] = []
            category_groups[category].append(item)
        grouping_time = time.time() - grouping_start
        
        # Test statistics calculation
        stats_start = time.time()
        total_items = len(test_items)
        unique_categories = len(category_groups)
        avg_items_per_category = total_items / unique_categories if unique_categories > 0 else 0
        stats_time = time.time() - stats_start
        
        total_time = time.time() - start_time
        
        return {
            "test_type": "large_dataset_handling",
            "dataset_size": len(test_items),
            "total_time_seconds": total_time,
            "parsing_time_seconds": parsing_time,
            "grouping_time_seconds": grouping_time,
            "stats_time_seconds": stats_time,
            "unique_categories": unique_categories,
            "avg_items_per_category": avg_items_per_category,
            "items_per_second": len(test_items) / total_time
        }
    
    def _generate_test_items(self, count: int) -> List[str]:
        """Generate test items for performance testing."""
        item_templates = [
            "Paint {color} {size}ltrs",
            "Wire {material} {gauge}mm {length}m",
            "Pipe {material} {diameter}mm {length}m",
            "Tool {type} {size} {brand}",
            "Safety {equipment} {color} {size}",
            "Steel {type} {diameter}mm {length}m",
            "Electrical {component} {rating} {brand}",
            "Plumbing {fitting} {size} {material}",
            "Wood {type} {dimensions} {grade}",
            "Hardware {item} {size} {finish}"
        ]
        
        colors = ["White", "Black", "Red", "Blue", "Green", "Yellow"]
        sizes = ["5", "10", "20", "25", "50", "100"]
        materials = ["Copper", "PVC", "Steel", "Aluminum", "Brass"]
        gauges = ["1.5", "2.5", "4", "6", "10", "16"]
        lengths = ["1", "2", "3", "5", "10", "20", "50", "100"]
        types = ["Hammer", "Screwdriver", "Drill", "Saw", "Wrench"]
        brands = ["BrandA", "BrandB", "BrandC", "BrandD"]
        diameters = ["12", "16", "20", "25", "32", "40", "50"]
        equipment = ["Helmet", "Gloves", "Vest", "Glasses", "Boots"]
        components = ["Switch", "Socket", "Fuse", "Breaker", "Relay"]
        ratings = ["10A", "16A", "20A", "32A", "63A"]
        fittings = ["Elbow", "Tee", "Coupling", "Adapter", "Valve"]
        grades = ["A", "B", "C", "Premium", "Standard"]
        items = ["Screw", "Bolt", "Nut", "Washer", "Bracket"]
        finishes = ["Zinc", "Chrome", "Black", "Silver", "Gold"]
        
        test_items = []
        for i in range(count):
            template = random.choice(item_templates)
            
            if "Paint" in template:
                item = template.format(color=random.choice(colors), size=random.choice(sizes))
            elif "Wire" in template:
                item = template.format(material=random.choice(materials), gauge=random.choice(gauges), length=random.choice(lengths))
            elif "Pipe" in template:
                item = template.format(material=random.choice(materials), diameter=random.choice(diameters), length=random.choice(lengths))
            elif "Tool" in template:
                item = template.format(type=random.choice(types), size=random.choice(sizes), brand=random.choice(brands))
            elif "Safety" in template:
                item = template.format(equipment=random.choice(equipment), color=random.choice(colors), size=random.choice(sizes))
            elif "Steel" in template:
                item = template.format(type="Bar", diameter=random.choice(diameters), length=random.choice(lengths))
            elif "Electrical" in template:
                item = template.format(component=random.choice(components), rating=random.choice(ratings), brand=random.choice(brands))
            elif "Plumbing" in template:
                item = template.format(fitting=random.choice(fittings), size=random.choice(sizes), material=random.choice(materials))
            elif "Wood" in template:
                item = template.format(type="Board", dimensions="100x50", grade=random.choice(grades))
            elif "Hardware" in template:
                item = template.format(item=random.choice(items), size=random.choice(sizes), finish=random.choice(finishes))
            else:
                item = f"Test Item {i+1}"
            
            test_items.append(item)
        
        return test_items
    
    async def _execute_category_search(self, query: str) -> Dict[str, Any]:
        """Execute a category search operation."""
        start_time = time.time()
        results = category_parser.search_categories(query)
        execution_time = time.time() - start_time
        
        return {
            "operation": "category_search",
            "query": query,
            "results_count": len(results),
            "execution_time_ms": execution_time * 1000
        }
    
    async def _execute_fuzzy_search(self, query: str) -> Dict[str, Any]:
        """Execute a fuzzy search operation."""
        start_time = time.time()
        try:
            results = await self.stock_query_service.fuzzy_search_items(query, limit=5)
            execution_time = time.time() - start_time
            
            return {
                "operation": "fuzzy_search",
                "query": query,
                "results_count": len(results),
                "execution_time_ms": execution_time * 1000
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "operation": "fuzzy_search",
                "query": query,
                "error": str(e),
                "execution_time_ms": execution_time * 1000
            }
    
    async def _execute_category_overview(self) -> Dict[str, Any]:
        """Execute a category overview operation."""
        start_time = time.time()
        try:
            results = await self.stock_query_service.get_category_overview()
            execution_time = time.time() - start_time
            
            return {
                "operation": "category_overview",
                "results_count": len(results) if isinstance(results, dict) else 0,
                "execution_time_ms": execution_time * 1000
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "operation": "category_overview",
                "error": str(e),
                "execution_time_ms": execution_time * 1000
            }
    
    async def _execute_category_statistics(self) -> Dict[str, Any]:
        """Execute a category statistics operation."""
        start_time = time.time()
        try:
            results = await self.query_service.get_category_statistics()
            execution_time = time.time() - start_time
            
            return {
                "operation": "category_statistics",
                "results_count": len(results.get("category_statistics", {})) if isinstance(results, dict) else 0,
                "execution_time_ms": execution_time * 1000
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "operation": "category_statistics",
                "error": str(e),
                "execution_time_ms": execution_time * 1000
            }
    
    def _generate_performance_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of performance test results."""
        summary = {
            "total_tests": len(results),
            "performance_metrics": {},
            "recommendations": []
        }
        
        # Analyze each test result
        for test_name, test_result in results.items():
            if "average_time_ms" in test_result:
                summary["performance_metrics"][test_name] = {
                    "average_time_ms": test_result["average_time_ms"],
                    "operations_per_second": test_result.get("items_per_second", test_result.get("queries_per_second", test_result.get("reports_per_second", 0)))
                }
        
        # Generate recommendations
        for test_name, metrics in summary["performance_metrics"].items():
            if metrics["average_time_ms"] > 100:  # More than 100ms
                summary["recommendations"].append(f"Consider optimizing {test_name} - current time: {metrics['average_time_ms']:.2f}ms")
            
            if metrics["operations_per_second"] < 10:  # Less than 10 ops/sec
                summary["recommendations"].append(f"Consider improving throughput for {test_name} - current rate: {metrics['operations_per_second']:.2f} ops/sec")
        
        return summary
    
    def get_performance_results(self) -> Dict[str, Any]:
        """Get the latest performance test results."""
        return self.performance_results
    
    def clear_results(self):
        """Clear performance test results."""
        self.performance_results.clear()
        logger.info("Performance test results cleared")
