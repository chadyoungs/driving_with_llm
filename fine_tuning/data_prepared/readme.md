Mature Driver Traits
> Rarely make unnecessary changes; only change when clear benefit exists.

Intent	
- Mandatory
  - Merge，ramp
  - Exit，ramp
  - Lane drop
  > cause, e.g. construction, road narrowing

- Voluntary 
  - Overtake
  ```
    slow lead vehicle in current lane
    target lane is clear
    ego vehicle accelerate after lane change
  ```
  - Maintain target speed move to faster lane
  - Space Optimization, Move to less crowded lane
  - Avoid obstacle, road debris, stopped vehicles
  - Avoid trucks
  - Avoid side-lane intrusion
  - Avoid sudden brake / close following/ congestion
  - Avoid VRU

- Unnecessary
  - Cutting off
  - Frequent lane hopping
  - Filtering in congestion
  - Abrupt lane change

- Else
  - Yield for emergency, e.g. ambulance, police car
  - Speed lane compilance

Execution	
> Smooth, well-planned changes; no abrupt swerves or reversals.
- Smooth 
  - low lateral acceleration, ≥2s duration
- Abrupt
  - high lateral acceleration, <1.5s duration
- Reversed
  - canceled mid-change

Context	
> Only change lanes when gaps are safe; avoid risky changes in congestion.
- Safe
  - gap ≥ 25m, TTC ≥3s
- Risky
  - gap < 15m, TTC <2s
- Congested
  - dense traffic

Todo
- Exits gap between the demo and industry product
  - consider the decision, actual lane change is also a time-series with multi states
  - real lane change consider more.
  Is the lane marking a solid line? (车道线是否实线？)

Is it a curved road? / Is it a bend? (是不是弯道？)

Is it a ramp? (是不是坡道？)

Is it a tunnel or a bridge? (是不是隧道 / 桥？)

Is it a construction zone? (是不是施工区？)

Is it an intersection? (是不是路口？)

Is it an emergency bay? / Is it the shoulder? (是不是紧急停车带？)

Is the adjacent lane ending? (相邻车道是不是即将消失？)

Is the ego-vehicle on a ramp / slip road? (自车是不是在匝道？)

Is there an accident or stationary vehicle ahead? (前方是否有事故 / 静止车？)

Is a high-speed vehicle approaching from the rear? (后方是否有快车逼近？)

Is the rear-lateral vehicle accelerating? (侧后车是否在加速？)

Is the crosswind too strong? / Is there an excessive crosswind? (横风是否过大？)

Is the steering wheel already turning? (方向盘是否已经在转动？)

Has the driver taken over? / Is there a driver intervention? (驾驶员是否接管？)

Is the brake pedal depressed? (刹车是否踩下？)

Is the turn signal on? / Is the blinker activated? (转向灯是否开启？)

Is the ego-acceleration profile smooth? (自车加速度是否平稳？)

Is the traffic flow speed in the target lane appropriate? (目标车道车流速度是否合适？)

Is it a consecutive lane change? (是否连续变道？)

- Long tail scenarios
  - exit congestion
  - construction
  - aggressive cut-in

- Models
  - intent prediction
  - map & localization fault tolerance

- Domain Adaptation
  - Unsupervised Domain Adaptation (UDA)
  - Multi-task learning
  - Simulation-Based RL Fine-tuning
