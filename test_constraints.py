#!/usr/bin/env python3
"""
Test script to verify that the time_series table constraints are properly set up.
"""

import asyncio
import sys
import os

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_plant_db
from utils.db_init import ensure_time_series_constraints
from sqlalchemy import text
from utils.log import setup_logger

logger = setup_logger(__name__)

async def test_constraints():
    """Test that the time_series table has proper constraints."""
    plant_id = "1"  # Test with plant 1
    
    logger.info(f"🔍 Testing constraints for Plant {plant_id}")
    
    async for session in get_plant_db(plant_id):
        try:
            # Check if the composite primary key constraint exists
            result = await session.execute(text("""
                SELECT constraint_name, constraint_type
                FROM information_schema.table_constraints 
                WHERE table_name = 'time_series' 
                AND constraint_type = 'PRIMARY KEY'
            """))
            constraints = result.fetchall()
            
            if constraints:
                logger.info(f"✅ Found {len(constraints)} primary key constraint(s):")
                for constraint in constraints:
                    logger.info(f"   - {constraint[0]} ({constraint[1]})")
            else:
                logger.warning("⚠️ No primary key constraints found on time_series table")
                
                # Try to create the constraint
                logger.info("🔧 Attempting to create the constraint...")
                await ensure_time_series_constraints(plant_id)
                
                # Check again
                result = await session.execute(text("""
                    SELECT constraint_name, constraint_type
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'time_series' 
                    AND constraint_type = 'PRIMARY KEY'
                """))
                constraints = result.fetchall()
                
                if constraints:
                    logger.info(f"✅ Successfully created {len(constraints)} primary key constraint(s):")
                    for constraint in constraints:
                        logger.info(f"   - {constraint[0]} ({constraint[1]})")
                else:
                    logger.error("❌ Failed to create primary key constraint")
            
            # Get a valid tag_id for testing
            result = await session.execute(text("SELECT id FROM tags LIMIT 1"))
            tag_result = result.fetchone()
            
            if not tag_result:
                logger.warning("⚠️ No tags found in database. Skipping ON CONFLICT test.")
                return
            
            valid_tag_id = tag_result[0]
            logger.info(f"🧪 Testing ON CONFLICT clause with tag_id {valid_tag_id}...")
            
            try:
                # First, try to insert a record
                await session.execute(text("""
                    INSERT INTO time_series (tag_id, timestamp, value, frequency)
                    VALUES (:tag_id, '2023-01-01 00:00:00', 'test', 'test')
                    ON CONFLICT (tag_id, timestamp) DO NOTHING
                """), {"tag_id": valid_tag_id})
                
                # Try to insert the same record again (should be ignored due to ON CONFLICT)
                await session.execute(text("""
                    INSERT INTO time_series (tag_id, timestamp, value, frequency)
                    VALUES (:tag_id, '2023-01-01 00:00:00', 'test2', 'test2')
                    ON CONFLICT (tag_id, timestamp) DO NOTHING
                """), {"tag_id": valid_tag_id})
                
                logger.info("✅ ON CONFLICT clause works correctly")
                
                # Clean up the test record
                await session.execute(text("""
                    DELETE FROM time_series 
                    WHERE tag_id = :tag_id AND timestamp = '2023-01-01 00:00:00'
                """), {"tag_id": valid_tag_id})
                
            except Exception as e:
                logger.error(f"❌ ON CONFLICT clause failed: {e}")
                await session.rollback()
                return
            
            await session.commit()
            logger.info("✅ All constraint tests passed!")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Error testing constraints: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(test_constraints()) 