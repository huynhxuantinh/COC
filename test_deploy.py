import logic
import numpy as np
import time
import random

class FakeADB:
    def click(self, x, y):
        print(f"  [ADB CLICK] -> ({x}, {y})")

class FakeVision:
    def __init__(self):
        pass
    def find_template(self, screen, template_name):
        return (500, 500)
    def read_troop_count(self, screen, center, offset):
        return 12 # Giả lập OCR đọc được 12 quân

def test():
    config = {
        "farm": {
            "troop_count_offset": [-45, -55, 10, -20],
            "troops": [
                {
                    "name": "sneaky_goblin",
                    "template": "sneaky_goblin_card.png",
                    "count": 5,
                    "pattern": "perimeter"
                },
                {
                    "name": "giant",
                    "template": "giant_card.png",
                    "count": 3,
                    "pattern": "edge_cluster"
                }
            ]
        },
        "battle": {
            "deploy_delay_min": 0.01,
            "deploy_delay_max": 0.02
        }
    }
    
    bot_logic = logic.BotLogic(adb=FakeADB(), vision=FakeVision(), config=config)
    
    # Giả lập màn hình 1920x1080
    screen = np.zeros((1080, 1920, 3), dtype=np.uint8)
    
    print("=== START TESTING DEPLOY TROOPS ===")
    bot_logic.deploy_troops(screen)
    print("=== TEST COMPLETED ===")

if __name__ == "__main__":
    test()
