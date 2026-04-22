const { Schema, model } = require('mongoose')

const orderSchema = new Schema(
	{
		user: { type: Schema.Types.ObjectId, ref: 'User' },
		product: { type: Schema.Types.ObjectId, ref: 'Product' },
		state: { type: Number },
		provider: { type: String },
	},
	{ timestamps: true }
)

module.exports = model('Order', orderSchema)
