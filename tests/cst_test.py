import win32com.client

# Start CST
cst = win32com.client.Dispatch("CSTStudio.Application")

# Create new project
project = cst.NewMWS()   # MWS = Microwave Studio

