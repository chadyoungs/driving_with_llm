import pygame
pygame.init()
screen = pygame.display.set_mode((400, 400))
clock = pygame.time.Clock()

# 绘制一个“长度沿X轴”的车辆矩形（默认朝右）
car_surface = pygame.Surface((45, 18), pygame.SRCALPHA)
pygame.draw.rect(car_surface, (255,0,0), (0,0,45,18))

running = True
while running:
    screen.fill((240,240,240))
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    
    # 1. 原始矩形（默认朝右）
    screen.blit(car_surface, (100, 200))
    # 2. 逆时针转90°（车头朝上）
    rotated_90 = pygame.transform.rotate(car_surface, 90)
    screen.blit(rotated_90, (200, 200))
    # 3. 逆时针转180°（车头朝左）
    rotated_180 = pygame.transform.rotate(car_surface, 180)
    screen.blit(rotated_180, (300, 200))

    pygame.display.flip()
    clock.tick(30)
pygame.quit()