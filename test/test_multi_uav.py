import airsim
client = airsim.MultirotorClient()
client.confirmConnection()
# 列出所有已加载的无人机
print("场景中的无人机列表：", client.listVehicles())